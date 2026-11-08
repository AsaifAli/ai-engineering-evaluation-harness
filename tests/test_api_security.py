from fastapi.testclient import TestClient

from app import auth, gateway
from app.main import app


def test_operational_post_routes_require_bearer_auth(monkeypatch):
    monkeypatch.setattr(auth, "HUB_API_KEY", "test-hub-secret")
    monkeypatch.setattr(gateway, "configured", lambda: False)

    headers = {"Authorization": "Bearer test-hub-secret"}

    cases = [
        ("/api/judge", {
            "target": "evidenceflow",
            "case_id": "security-test",
            "answer": "Test answer",
            "reference": "Test reference",
            "context": ["Test evidence"],
        }),
        ("/ai/triage", {"title": "Test engineering issue"}),
        ("/ai/pr-review", {"title": "Test pull request"}),
        ("/api/ai-quality/run?target=all", {}),
        ("/webhooks/n8n", {"event": "security-test"}),
        ("/ai/experiment-summary", {
            "experiment": "security-test",
            "metrics": {"recall@5": 0.95},
        }),
        ("/approvals", {
            "workflow": "security-test",
            "summary": "Test approval",
            "payload": {},
        }),
    ]

    with TestClient(app) as client:
        approval_id = None

        for path, payload in cases:
            missing = client.post(path, json=payload)
            assert missing.status_code == 401, path

            invalid = client.post(
                path,
                json=payload,
                headers={"Authorization": "Bearer wrong-key"},
            )
            assert invalid.status_code == 401, path

            valid = client.post(path, json=payload, headers=headers)
            assert valid.status_code == 200, (path, valid.text)

            if path == "/approvals":
                approval_id = valid.json()["approval_id"]

        decision_path = f"/approvals/{approval_id}/decision"
        decision = {"status": "approved", "decided_by": "tester"}

        assert client.post(decision_path, json=decision).status_code == 401

        assert client.post(
            decision_path,
            json=decision,
            headers={"Authorization": "Bearer wrong-key"},
        ).status_code == 401

        assert client.post(
            decision_path,
            json=decision,
            headers=headers,
        ).status_code == 200
