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

    monkeypatch.setattr(auth, "HUB_API_KEY", "operator-secret")
    monkeypatch.setattr(config, "HUB_IP_RATE_LIMIT_PER_MINUTE", 1)
    rate_limiter.clear()

    with TestClient(app) as client:
        first = client.post("/api/ai-quality/run?target=all")
        second = client.post("/api/ai-quality/run?target=all")

    assert first.status_code == 401
    assert second.status_code == 429
    assert second.headers["retry-after"]


def test_write_routes_reject_oversized_chunked_body():
    import asyncio

    from app.main import RequestBodySizeLimitMiddleware

    downstream_read = False
    sent_messages = []
    incoming = [
        {"type": "http.request", "body": b"1234", "more_body": True},
        {"type": "http.request", "body": b"5678", "more_body": False},
    ]

    async def downstream(scope, receive, send):
        nonlocal downstream_read
        while True:
            message = await receive()
            if message["type"] == "http.request":
                downstream_read = True
                if not message.get("more_body", False):
                    return

    async def receive():
        return incoming.pop(0)

    async def send(message):
        sent_messages.append(message)

    middleware = RequestBodySizeLimitMiddleware(downstream, max_bytes=5)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/application-events",
        "headers": [],
    }

    asyncio.run(middleware(scope, receive, send))

    assert downstream_read is True
    assert sent_messages[0]["status"] == 413
    assert b"Request body too large" in sent_messages[1]["body"]


def test_write_routes_reject_oversized_declared_body_before_downstream():
    import asyncio

    from app.main import RequestBodySizeLimitMiddleware

    downstream_called = False
    sent_messages = []

    async def downstream(scope, receive, send):
        nonlocal downstream_called
        downstream_called = True

    async def receive():
        raise AssertionError("Oversized declared body must be rejected early.")

    async def send(message):
        sent_messages.append(message)

    middleware = RequestBodySizeLimitMiddleware(downstream, max_bytes=5)
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/application-events",
        "headers": [(b"content-length", b"6")],
    }

    asyncio.run(middleware(scope, receive, send))

    assert downstream_called is False
    assert sent_messages[0]["status"] == 413


def test_flowpilot_project_ingest_uses_its_own_project_token(monkeypatch):
    from app import main

    monkeypatch.setattr(
        config,
        "HARNESS_INGEST_TOKENS_JSON",
        '{"evidenceflow":"evidence-token","quotesense":"quote-token","flowpilot":"flowpilot-token"}',
    )
    monkeypatch.setattr(main, "insert_application_event", lambda **kwargs: True)
    payload = {
        "event_id": "fp-" + "f" * 32,
        "project": "flowpilot",
        "event_type": "run.completed",
        "status": "success",
        "workflow": "content",
        "duration_ms": 123.0,
        "metrics": {"draft_count": 2, "approval_required": True},
    }

    with TestClient(app) as client:
        wrong = client.post(
            "/api/application-events",
            headers={"Authorization": "Bearer quote-token"},
            json=payload,
        )
        accepted = client.post(
            "/api/application-events",
            headers={"Authorization": "Bearer flowpilot-token"},
            json=payload,
        )

    assert wrong.status_code == 401
    assert accepted.status_code == 202
    assert accepted.json()["accepted"] is True
