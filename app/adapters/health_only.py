from __future__ import annotations

from typing import Any

from ..harness import AgentRun, AdapterError, HttpAIProjectAdapter
from ..targets import TargetSpec, configured_target_url


class HealthOnlyAdapter(HttpAIProjectAdapter):
    """Adapter for AI projects whose hosted surface exposes health but no stable run API yet."""

    def __init__(self, spec: TargetSpec):
        base_url = configured_target_url(spec)
        if not base_url:
            raise AdapterError(f"{spec.name} is not configured")
        super().__init__(base_url, timeout=30.0)
        self.spec = spec
        self.name = spec.slug

    async def health(self) -> dict[str, Any]:
        return await self.request("GET", self.spec.health_path)

    async def run(self, workflow: str, payload: dict[str, Any]) -> AgentRun:
        raise AdapterError(
            f"{self.spec.name} exposes a health surface but no stable execution API is registered in the harness. "
            "Use replay mode or add a project-specific adapter when an execution endpoint is available."
        )
