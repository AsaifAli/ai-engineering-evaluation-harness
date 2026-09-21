from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class AdapterError(RuntimeError):
    pass


@dataclass
class AgentRun:
    run_id: str
    workflow: str
    status: str
    output: dict[str, Any]
    duration_ms: int = 0
    usage: dict[str, Any] | None = None
    warnings: list[str] | None = None
    trace: list[dict[str, Any]] | None = None
    metadata: dict[str, Any] | None = None


class AIProjectAdapter(Protocol):
    name: str

    async def run(self, workflow: str, payload: dict[str, Any]) -> AgentRun:
        ...


class HttpAIProjectAdapter:
    """Base adapter for wrapping an existing AI application as a harness target."""

    name = "http-project"

    def __init__(self, base_url: str, *, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, f"{self.base_url}{path}", **kwargs)
        except httpx.HTTPError as exc:
            raise AdapterError(f"Target request failed: {exc}") from exc
        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise AdapterError(f"Target returned HTTP {response.status_code}: {detail}")
        try:
            return response.json()
        except ValueError as exc:
            raise AdapterError("Target returned non-JSON content") from exc


async def timed_run(adapter: AIProjectAdapter, workflow: str, payload: dict[str, Any]) -> AgentRun:
    """Standard harness entry point: assign a harness run id and measure wall time."""
    started = time.perf_counter()
    harness_run_id = str(uuid.uuid4())
    result = await adapter.run(workflow, payload)
    if result.duration_ms <= 0:
        result.duration_ms = round((time.perf_counter() - started) * 1000)
    if not result.run_id:
        result.run_id = harness_run_id
    return result
