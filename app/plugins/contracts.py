from __future__ import annotations

from typing import Any, Protocol

from ..harness import AgentRun


class ProjectAdapterPlugin(Protocol):
    """Contract implemented by a project integration plugin."""

    name: str

    async def run(self, workflow: str, payload: dict[str, Any]) -> AgentRun:
        ...
