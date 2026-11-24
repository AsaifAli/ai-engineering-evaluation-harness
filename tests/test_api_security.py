from fastapi.testclient import TestClient

from app import auth, config
from app.main import app


def test_operator_key_is_required_for_replay_write(monkeypatch):
    monkeypatch.setattr(auth, "HUB_API_KEY", "operator-secret")
    with TestClient(app) as client:
        assert client.post("/api/ai-quality/run?target=all").status_code == 401
        assert client.post(
            "/api/ai-quality/run?target=all",
            headers={"Authorization": "Bearer wrong"},
        ).status_code == 401
        allowed = client.post(
            "/api/ai-quality/run?target=all",
            headers={"Authorization": "Bearer operator-secret"},
        )
        assert allowed.status_code == 200


def test_application_ingest_uses_project_scoped_tokens(monkeypatch):
    monkeypatch.setattr(
        config,
        "HARNESS_INGEST_TOKENS_JSON",
        '{"evidenceflow":"evidence-token","quotesense":"quote-token"}',
    )
    payload = {
        "event_id": "ef-" + "a" * 32,
        "project": "evidenceflow",
        "event_type": "run.completed",
        "status": "success",
        "workflow": "rag_query",
        "duration_ms": 421.5,
        "model": "model-label",
        "metrics": {"retrieved_chunks": 5, "evidence_audit_pass": True},
    }
    with TestClient(app) as client:
        missing = client.post("/api/application-events", json=payload)
        assert missing.status_code == 401
        wrong = client.post(
            "/api/application-events",
            headers={"Authorization": "Bearer quote-token"},
            json=payload,
        )
        assert wrong.status_code == 401
        accepted = client.post(
            "/api/application-events",
            headers={"Authorization": "Bearer evidence-token"},
            json=payload,
        )
        assert accepted.status_code == 202
        assert accepted.json()["accepted"] is True
        duplicate = client.post(
            "/api/application-events",
            headers={"Authorization": "Bearer evidence-token"},
            json=payload,
        )
        assert duplicate.status_code == 202
        assert duplicate.json()["duplicate"] is True


def test_ingest_rejects_content_fields_and_invalid_metrics(monkeypatch):
    monkeypatch.setattr(
        config,
        "HARNESS_INGEST_TOKENS_JSON",
        '{"quotesense":"quote-token"}',
    )
    payload = {
        "event_id": "qs-" + "b" * 32,
        "project": "quotesense",
        "event_type": "run.completed",
        "status": "success",
        "workflow": "quotation_analysis",
        "prompt": "sensitive source text must never be ingested",
    }
    with TestClient(app) as client:
        response = client.post(
            "/api/application-events",
            headers={"Authorization": "Bearer quote-token"},
            json=payload,
        )
        assert response.status_code == 422

        payload.pop("prompt")
        payload["metrics"] = {"source_text": "raw content"}
        response = client.post(
            "/api/application-events",
            headers={"Authorization": "Bearer quote-token"},
            json=payload,
        )
        assert response.status_code == 422
