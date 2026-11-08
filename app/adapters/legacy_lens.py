from __future__ import annotations

import asyncio
import json
from typing import Any

from .. import config
from ..harness import AgentRun, AdapterError, HttpAIProjectAdapter


def _parse_object(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else None
        except (ValueError, TypeError):
            return None

    return None


class LegacyLensAdapter(HttpAIProjectAdapter):
    """Adapter for LegacyLens task execution and progress telemetry."""

    name = "legacylens"

    def __init__(self) -> None:
        super().__init__(
            config.LEGACY_LENS_BASE_URL,
            timeout=config.LEGACY_LENS_TIMEOUT,
        )

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
                "LegacyLens live execution requires LEGACY_LENS_AUTHORIZATION "
                "and LEGACY_LENS_GATEWAY_TOKEN."
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

        last: dict[str, Any] = {}
        trace: list[dict[str, Any]] = []

        for _ in range(120):
            last = await self.request(
                "GET",
                f"/v1/tasks/{task_id}",
                headers=self.headers,
            )

            progress = _parse_object(last.get("result"))

            if progress and progress.get("kind") == "progress":
                event = {
                    "event_type": "workflow_progress",
                    "stage": progress.get("stage"),
                    "percent": progress.get("percent"),
                    "message": progress.get("message"),
                    "plan": progress.get("plan", []),
                }

                if not trace or trace[-1] != event:
                    trace.append(event)

            status = str(last.get("status") or "")

            if status in {"completed", "failed", "error"}:
                break

            await asyncio.sleep(0.5)
        else:
            raise AdapterError(
                f"LegacyLens task {task_id} did not complete within timeout"
            )

        task_result = _parse_object(last.get("result")) or {}
        final_output = _parse_object(task_result.get("output"))

        output = final_output or {}

        for step in task_result.get("plan", []):
            if isinstance(step, dict):
                trace.append({
                    "event_type": "workflow_step",
                    "step_name": step.get("name"),
                    "status": step.get("status"),
                    "progress_percent": step.get("percent"),
                    "source": "final_task_plan",
                })

        release_ready = task_result.get("release_ready")

        trace.append({
            "event_type": "task_outcome",
            "status": status,
            "completion_kind": task_result.get("kind"),
            "release_ready": release_ready,
        })

        metadata = {
            key: value
            for key, value in {
                "release_ready": release_ready,
                "completion_kind": task_result.get("kind"),
                "quality_gate": output.get("quality_gate"),
                "message": task_result.get("message"),
            }.items()
            if value is not None
        }

        warnings = []
        if last.get("error"):
            warnings.append(str(last["error"]))

        return AgentRun(
            run_id=task_id,
            workflow=workflow,
            status=status,
            output=output,
            warnings=warnings,
            trace=trace,
            metadata=metadata,
        )