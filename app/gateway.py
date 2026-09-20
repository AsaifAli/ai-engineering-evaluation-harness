from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx


class GatewayError(RuntimeError):
    pass


GATEWAY_BASE_URL = os.getenv(
    "GATEWAY_BASE_URL",
    "https://portfolio-llm-gateway.onrender.com",
).rstrip("/")

GATEWAY_SESSION_TOKEN = os.getenv("GATEWAY_SESSION_TOKEN", "").strip()
GATEWAY_TIMEOUT = float(os.getenv("GATEWAY_TIMEOUT", "45"))
GATEWAY_MODEL = os.getenv("GATEWAY_MODEL", "").strip()


def gateway_configured() -> bool:
    return bool(GATEWAY_SESSION_TOKEN)


def _extract_json(content: str) -> dict[str, Any]:
    text = content.strip()

    # Remove markdown code fences if the model adds them.
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    # Try extracting the outermost JSON object.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            value = json.loads(text[start : end + 1])
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass

    raise GatewayError("Gateway returned a non-JSON model response")


async def chat_json(
    *,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.1,
) -> dict[str, Any]:
    if not GATEWAY_SESSION_TOKEN:
        raise GatewayError("Gateway session token is not configured")

    payload: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": 1200,
    }

    if GATEWAY_MODEL:
        payload["model"] = GATEWAY_MODEL

    headers = {
        "Authorization": f"Bearer {GATEWAY_SESSION_TOKEN}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=GATEWAY_TIMEOUT) as client:
            response = await client.post(
                f"{GATEWAY_BASE_URL}/v1/chat/completions",
                headers=headers,
                json=payload,
            )
    except httpx.HTTPError as exc:
        raise GatewayError(f"Gateway request failed: {exc}") from exc

    if response.status_code != 200:
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        raise GatewayError(
            f"Gateway returned HTTP {response.status_code}: {detail}"
        )

    try:
        body = response.json()
        content = body["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise GatewayError("Gateway returned an unexpected response shape") from exc

    if not isinstance(content, str):
        raise GatewayError("Gateway returned non-text model content")

    return _extract_json(content)
