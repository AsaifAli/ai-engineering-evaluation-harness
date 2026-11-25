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


def test_replay_endpoint_is_rate_limited_per_operator_key(monkeypatch):
    from app import main
    from app.rate_limit import rate_limiter

    monkeypatch.setattr(auth, "HUB_API_KEY", "operator-secret")
    monkeypatch.setattr(config, "HUB_RATE_LIMIT_PER_MINUTE", 1)
    monkeypatch.setattr(config, "HUB_IP_RATE_LIMIT_PER_MINUTE", 20)
    monkeypatch.setattr(main, "run_all", lambda mode: {"mode": mode})
    rate_limiter.clear()

    with TestClient(app) as client:
        headers = {"Authorization": "Bearer operator-secret"}
        first = client.post("/api/ai-quality/run?target=all", headers=headers)
        second = client.post("/api/ai-quality/run?target=all", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["retry-after"]


def test_project_ingest_is_rate_limited_per_project_token(monkeypatch):
    from app import main
    from app.rate_limit import rate_limiter

    monkeypatch.setattr(
        config,
        "HARNESS_INGEST_TOKENS_JSON",
        '{"evidenceflow":"evidence-token"}',
    )
    monkeypatch.setattr(config, "PROJECT_INGEST_RATE_LIMIT_PER_MINUTE", 1)
    monkeypatch.setattr(config, "HUB_IP_RATE_LIMIT_PER_MINUTE", 20)
    monkeypatch.setattr(main, "insert_application_event", lambda **kwargs: True)
    rate_limiter.clear()

    payload = {
        "event_id": "ef-" + "c" * 32,
        "project": "evidenceflow",
        "event_type": "run.completed",
        "status": "success",
        "workflow": "rag_query",
        "metrics": {"retrieved_chunks": 1},
    }
    with TestClient(app) as client:
        headers = {"Authorization": "Bearer evidence-token"}
        first = client.post("/api/application-events", headers=headers, json=payload)
        second = client.post("/api/application-events", headers=headers, json={
            **payload, "event_id": "ef-" + "d" * 32
        })

    assert first.status_code == 202
    assert second.status_code == 429
    assert second.headers["retry-after"]


def test_write_routes_rate_limit_invalid_auth_by_client_ip(monkeypatch):
    from app.rate_limit import rate_limiter

    monkeypatch.setattr(config, "HUB_IP_RATE_LIMIT_PER_MINUTE", 1)
    rate_limiter.clear()

    with TestClient(app) as client:
        first = client.post("/api/ai-quality/run?target=all")
        second = client.post("/api/ai-quality/run?target=all")

    assert first.status_code == 401
    assert second.status_code == 429
    assert second.headers["retry-after"]
