from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from .config import (
    CIRCUIT_FAILURE_THRESHOLD,
    CIRCUIT_RECOVERY_SECONDS,
    GATEWAY_BASE_URL,
    GATEWAY_MAX_RETRIES,
    GATEWAY_MODEL,
    GATEWAY_SESSION_TOKEN,
    GATEWAY_TIMEOUT,
    MODEL_PRICING_JSON,
)


class GatewayError(RuntimeError):
    pass


class CircuitOpenError(GatewayError):
    pass


@dataclass
class GatewayResponse:
    data: dict[str, Any]
    provider: str
    model: str
    prompt_tokens: Optional[int]
    output_tokens: Optional[int]
    total_tokens: Optional[int]
    estimated_cost_usd: Optional[float]
    latency_ms: float
    request_id: Optional[str]


class CircuitBreaker:
    def __init__(self, threshold: int, recovery_seconds: float) -> None:
        self.threshold = threshold
        self.recovery_seconds = recovery_seconds
        self.failures = 0
        self.opened_at: Optional[float] = None

    def before_call(self) -> None:
        if self.opened_at is None:
            return
        elapsed = time.monotonic() - self.opened_at
        if elapsed < self.recovery_seconds:
            raise CircuitOpenError("LLM gateway circuit is open")
        self.opened_at = None
        self.failures = 0

    def success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = time.monotonic()

    @property
    def state(self) -> str:
        if self.opened_at is not None:
            return "open"
        if self.failures:
            return "degraded"
        return "closed"


circuit = CircuitBreaker(CIRCUIT_FAILURE_THRESHOLD, CIRCUIT_RECOVERY_SECONDS)


def configured() -> bool:
    return bool(GATEWAY_SESSION_TOKEN)


def status() -> dict[str, Any]:
    return {
        "configured": configured(),
        "base_url": GATEWAY_BASE_URL,
        "model": GATEWAY_MODEL or "session-selected",
        "circuit": circuit.state,
    }


def _extract_content(body: dict[str, Any]) -> str:
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise GatewayError("Gateway response did not contain choices[0].message.content") from exc
    if isinstance(content, list):
        content = "".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in content)
    if not isinstance(content, str):
        raise GatewayError("Gateway returned non-text content")
    return content


def _extract_json(content: str) -> dict[str, Any]:
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start:end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    raise GatewayError("Gateway returned invalid JSON")


def _pricing(model: str, input_tokens: Optional[int], output_tokens: Optional[int]) -> Optional[float]:
    if not input_tokens and not output_tokens:
        return None
    try:
        prices = json.loads(MODEL_PRICING_JSON)
        price = prices.get(model) or prices.get("default")
        if not isinstance(price, dict):
            return None
        in_rate = float(price.get("input_per_1k", 0))
        out_rate = float(price.get("output_per_1k", 0))
        return round((input_tokens or 0) / 1000 * in_rate + (output_tokens or 0) / 1000 * out_rate, 8)
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


async def chat_json(*, system_prompt: str, user_prompt: str, workflow: str, prompt_version: str) -> GatewayResponse:
    if not configured():
        raise GatewayError("Gateway session token is not configured")
    circuit.before_call()
    payload: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.1,
        "max_tokens": 1400,
    }
    if GATEWAY_MODEL:
        payload["model"] = GATEWAY_MODEL
    headers = {"Authorization": f"Bearer {GATEWAY_SESSION_TOKEN}", "Content-Type": "application/json"}
    last_error: Optional[Exception] = None
    started = time.perf_counter()
    for attempt in range(GATEWAY_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=GATEWAY_TIMEOUT) as client:
                response = await client.post(f"{GATEWAY_BASE_URL}/v1/chat/completions", headers=headers, json=payload)
            if response.status_code in {408, 429, 500, 502, 503, 504} and attempt < GATEWAY_MAX_RETRIES:
                await asyncio.sleep(0.25 * (2 ** attempt))
                continue
            if response.status_code != 200:
                try:
                    detail = response.json()
                except ValueError:
                    detail = response.text
                raise GatewayError(f"Gateway HTTP {response.status_code}: {detail}")
            body = response.json()
            parsed = _extract_json(_extract_content(body))
            usage = body.get("usage") or {}
            prompt_tokens = usage.get("prompt_tokens")
            output_tokens = usage.get("completion_tokens") or usage.get("output_tokens")
            total_tokens = usage.get("total_tokens")
            model = body.get("model") or GATEWAY_MODEL or "session-selected"
            latency_ms = round((time.perf_counter() - started) * 1000, 2)
            circuit.success()
            return GatewayResponse(
                data=parsed,
                provider="gateway",
                model=model,
                prompt_tokens=prompt_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                estimated_cost_usd=_pricing(model, prompt_tokens, output_tokens),
                latency_ms=latency_ms,
                request_id=response.headers.get("x-request-id") or body.get("id"),
            )
        except (httpx.HTTPError, ValueError, GatewayError) as exc:
            last_error = exc
            if isinstance(exc, GatewayError) and attempt >= GATEWAY_MAX_RETRIES:
                break
            if attempt >= GATEWAY_MAX_RETRIES:
                break
            await asyncio.sleep(0.25 * (2 ** attempt))
    circuit.failure()
    raise GatewayError(str(last_error or "Gateway request failed"))
