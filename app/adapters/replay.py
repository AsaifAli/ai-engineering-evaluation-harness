from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..harness import AgentRun, AdapterError


class ReplayAdapter:
    """Deterministic adapter that replays a versioned project fixture.

    Replay mode is deliberately explicit: it is a validation path for the harness,
    not a claim that the hosted application was executed live.
    """

    def __init__(self, target: str, dataset_path: str | Path):
        self.target = target
        self.dataset_path = Path(dataset_path)
        self.name = target

    def cases(self) -> list[dict[str, Any]]:
        if not self.dataset_path.exists():
            raise AdapterError(f"Replay dataset not found: {self.dataset_path}")
        data = json.loads(self.dataset_path.read_text())
        if not isinstance(data, list):
            raise AdapterError(f"Replay dataset must be a list: {self.dataset_path}")
        return data

    async def run(self, workflow: str, payload: dict[str, Any]) -> AgentRun:
        cases = self.cases()
        case_id = str(payload.get("case_id") or (cases[0].get("id") if cases else ""))
        case = next((item for item in cases if str(item.get("id")) == case_id), None)
        if case is None:
            raise AdapterError(f"Replay case not found for {self.target}: {case_id}")
        return AgentRun(
            run_id=f"replay-{self.target}-{case_id}",
            workflow=workflow,
            status="completed",
            output=case.get("actual") or {},
            duration_ms=int(case.get("duration_ms") or 0),
            usage=None,
            warnings=["replay_mode: fixture data, not live target execution"],
        )
