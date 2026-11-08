import asyncio
import json

import pytest

from app import config
from app.adapters.legacy_lens import LegacyLensAdapter
from app.harness import AdapterError


class FakeLegacyLensAdapter(LegacyLensAdapter):
    def __init__(self, responses):
        super().__init__()
        self.responses = list(responses)
        self.calls = []

    async def request(self, method, path, **kwargs):
        self.calls.append((method, path))
        if not self.responses:
            raise AssertionError("Unexpected HTTP request")
        return self.responses.pop(0)


def setup_credentials(monkeypatch):
    monkeypatch.setattr(config, "LEGACY_LENS_AUTHORIZATION", "Bearer test-user")
    monkeypatch.setattr(config, "LEGACY_LENS_GATEWAY_TOKEN", "test-gateway-token")


def test_legacylens_captures_progress_and_successful_release(monkeypatch):
    setup_credentials(monkeypatch)

    progress = {
        "kind": "progress",
        "stage": "workflow",
        "percent": 50,
        "message": "Running migration planning",
        "plan": [{"name": "Plan migration", "status": "running", "percent": 50}],
    }

    final_output = {
        "status": "ready",
        "release_ready": True,
        "quality_gate": {"release_ready": True},
    }

    completed = {
        "kind": "completed",
        "output": json.dumps(final_output),
        "release_ready": True,
        "message": "Migration passed the release gate.",
        "plan": [{"name": "Convert code", "status": "complete", "percent": 100}],
    }

    adapter = FakeLegacyLensAdapter([
        {"task_id": "task-123"},
        {"status": "running", "result": json.dumps(progress)},
        {"status": "completed", "result": json.dumps(completed)},
    ])

    result = asyncio.run(adapter.run("migration", {"source_path": "/tmp/source"}))

    assert result.run_id == "task-123"
    assert result.status == "completed"
    assert result.output["release_ready"] is True
    assert result.metadata["release_ready"] is True
    assert any(step["event_type"] == "workflow_progress" for step in result.trace)
    assert any(step["event_type"] == "workflow_step" for step in result.trace)
    assert result.trace[-1]["event_type"] == "task_outcome"


def test_legacylens_preserves_blocked_release_outcome(monkeypatch):
    setup_credentials(monkeypatch)

    blocked = {
        "kind": "blocked",
        "output": json.dumps({
            "status": "blocked",
            "release_ready": False,
            "quality_gate": {"release_ready": False},
        }),
        "release_ready": False,
        "message": "Post-migration quality gate failed.",
        "plan": [],
    }

    adapter = FakeLegacyLensAdapter([
        {"task_id": "task-456"},
        {"status": "failed", "result": json.dumps(blocked),
         "error": "Post-migration quality gate failed."},
    ])

    result = asyncio.run(adapter.run("migration", {}))

    assert result.status == "failed"
    assert result.metadata["release_ready"] is False
    assert result.output["quality_gate"]["release_ready"] is False
    assert result.warnings


def test_legacylens_rejects_missing_credentials(monkeypatch):
    monkeypatch.setattr(config, "LEGACY_LENS_AUTHORIZATION", "")
    monkeypatch.setattr(config, "LEGACY_LENS_GATEWAY_TOKEN", "")

    adapter = FakeLegacyLensAdapter([])

    with pytest.raises(AdapterError, match="requires"):
        asyncio.run(adapter.run("migration", {}))