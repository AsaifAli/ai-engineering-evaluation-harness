from __future__ import annotations

import asyncio
from typing import Any

from ..config import COMMAND_CENTER_API_KEY, COMMAND_CENTER_BASE_URL, COMMAND_CENTER_LLM_GATEWAY_TOKEN, COMMAND_CENTER_TIMEOUT
from ..harness import AgentRun, AdapterError, HttpAIProjectAdapter


class CommandCenterAdapter(HttpAIProjectAdapter):
    """Adapter for the user's AI Automation Command Center control-plane API."""

    name = "ai-automation-command-center"

    def __init__(self) -> None:
        super().__init__(COMMAND_CENTER_BASE_URL, timeout=COMMAND_CENTER_TIMEOUT)

    @property
    def headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if COMMAND_CENTER_API_KEY:
            headers["X-API-Key"] = COMMAND_CENTER_API_KEY
        if COMMAND_CENTER_LLM_GATEWAY_TOKEN:
            headers["X-LLM-Gateway-Token"] = COMMAND_CENTER_LLM_GATEWAY_TOKEN
        return headers

    async def run(self, workflow: str, payload: dict[str, Any]) -> AgentRun:
        created = await self.request(
            "POST",
            "/api/v1/runs",
            headers=self.headers,
            json={"workflow": workflow, "payload": payload},
        )
        run_id = str(created.get("run_id") or "")
        if not run_id:
            raise AdapterError("Command Center did not return run_id")

        last: dict[str, Any] = created
        for _ in range(60):
            last = await self.request("GET", f"/api/v1/runs/{run_id}", headers=self.headers)
            status = str(last.get("status", ""))
            if status in {"completed", "completed_with_warnings", "failed"}:
                break
            await asyncio.sleep(0.5)
        else:
            raise AdapterError(f"Command Center run {run_id} did not complete within timeout")

        return AgentRun(
            run_id=run_id,
            workflow=workflow,
            status=str(last.get("status", "unknown")),
            output=last.get("output") or {},
            duration_ms=int(last.get("duration_ms") or 0),
            usage=last.get("usage"),
            warnings=last.get("warnings") or [],
            trace=last.get("trace") if isinstance(last.get("trace"), list) else last.get("steps") if isinstance(last.get("steps"), list) else [],
            metadata={k: last.get(k) for k in ("prompt_version", "model_version", "config_version") if last.get(k) not in (None, "")},
        )
