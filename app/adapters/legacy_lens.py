from __future__ import annotations

import asyncio
from typing import Any

from .. import config
from ..harness import AgentRun, AdapterError, HttpAIProjectAdapter


class LegacyLensAdapter(HttpAIProjectAdapter):
    """Adapter for the LegacyLens agent_service task API.

    Live execution requires the same authenticated user + short-lived portfolio
    gateway token that LegacyLens expects. The harness therefore defaults to
    health/readiness validation until those credentials are supplied.
    """

    name = "legacylens"

    def __init__(self) -> None:
        super().__init__(config.LEGACY_LENS_BASE_URL, timeout=config.LEGACY_LENS_TIMEOUT)

    @property
    def headers(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if config.LEGACY_LENS_AUTHORIZATION:
            headers["Authorization"] = config.LEGACY_LENS_AUTHORIZATION
        if config.LEGACY_LENS_GATEWAY_TOKEN:
            headers["X-LLM-Gateway-Token"] = config.LEGACY_LENS_GATEWAY_TOKEN
        return headers

    async def health(self) -> dict[str, Any]:
        return await self.request("GET", "/healthz")

    async def readiness(self) -> dict[str, Any]:
        return await self.request("GET", "/readyz")

    async def run(self, workflow: str, payload: dict[str, Any]) -> AgentRun:
        if not config.LEGACY_LENS_AUTHORIZATION or not config.LEGACY_LENS_GATEWAY_TOKEN:
            raise AdapterError(
                "LegacyLens live execution requires LEGACY_LENS_AUTHORIZATION and "
                "LEGACY_LENS_GATEWAY_TOKEN. Health validation does not require them."
            )

        accepted = await self.request(
            "POST",
            "/v1/teams/run",
            headers={**self.headers, "Content-Type": "application/json"},
            json=payload,
        )
        task_id = str(accepted.get("task_id") or "")
        if not task_id:
            raise AdapterError("LegacyLens did not return task_id")

        last: dict[str, Any] = accepted
        for _ in range(120):
            last = await self.request("GET", f"/v1/tasks/{task_id}", headers=self.headers)
            status = str(last.get("status") or "")
            if status in {"completed", "failed", "error"}:
                break
            await asyncio.sleep(0.5)
        else:
            raise AdapterError(f"LegacyLens task {task_id} did not complete within timeout")

        return AgentRun(
            run_id=task_id,
            workflow=workflow,
            status=str(last.get("status", "unknown")),
            output=last.get("result") or {},
            warnings=[] if not last.get("error") else [str(last.get("error"))],
        )
