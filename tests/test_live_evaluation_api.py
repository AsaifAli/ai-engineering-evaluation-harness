import json
import uuid

from fastapi.testclient import TestClient

from app import auth
from app.db import query_rows, query_traces
from app.harness import AgentRun
from app.main import app
import app.main as main_module


class FakeLegacyLensAdapter:
    async def run(self, workflow, payload):
        quality_gate = {
            "status": "passed",
            "release_ready": True,
            "quality_score": 92.0,
            "checks": [
                {"name": "syntax", "required": True, "status": "passed"},
                {"name": "unit-tests", "required": True, "status": "passed"},
            ],
            "semantic_gate": {
                "status": "passed",
                "semantic_status": "verified",
            },
            "repair_history": [],
        }

        return AgentRun(
            run_id="test-live-" + str(uuid.uuid4()),
            workflow=workflow,
            status="completed",
            output={
                "status": "ready",
                "release_ready": True,
                "quality_gate": quality_gate,
                "semantic_verification": {"status": "verified"},
            },
            duration_ms=1250,
            trace=[
                {
                    "event_type": "workflow_step",
                    "step_name": "Convert code",
                    "status": "complete",
                }
            ],
            metadata={
                "release_ready": True,
                "quality_gate": quality_gate,
            },
        )


def test_live_legacy_evaluation_is_returned_and_persisted(monkeypatch):
    monkeypatch.setattr(auth, "HUB_API_KEY", "test-hub-secret")
    monkeypatch.setattr(
        main_module, "live_adapter", lambda target: FakeLegacyLensAdapter()
    )

    headers = {"Authorization": "Bearer test-hub-secret"}

    with TestClient(app) as client:
        response = client.post(
            "/api/targets/legacylens/run?mode=live",
            headers=headers,
            json={"workflow": "migration"},
        )

    assert response.status_code == 200, response.text
    body = response.json()

    evaluation = body["live_evaluation"]

    assert evaluation["evaluation_type"] == "live_trajectory"
    assert evaluation["evaluation_status"] == "complete"
    assert evaluation["passed"] is True
    assert evaluation["score"] == 0.92
    assert evaluation["score_percent"] == 92.0

    traces = query_traces(run_id=body["run_id"])
    assert traces
    assert traces[0]["metadata"]["live_evaluation"] == evaluation

    audit_events = query_rows("audit_events", 200)
    audit_event = next(
        item for item in audit_events
        if item.get("run_id") == body["run_id"]
        and item.get("event_type") == "target_run"
    )

    audit_payload = json.loads(audit_event["payload"])
    assert audit_payload["live_evaluation"] == evaluation