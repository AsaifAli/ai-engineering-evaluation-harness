import uuid

from fastapi.testclient import TestClient

from app import auth, config
from app.main import app


def test_health_and_readiness():
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json()["database"] == "ok"


def test_replay_evaluation_is_limited_to_the_two_connected_apps(monkeypatch):
    monkeypatch.setattr(auth, "HUB_API_KEY", "operator-test-token")
    headers = {"Authorization": "Bearer operator-test-token"}
    with TestClient(app) as client:
        denied = client.post("/api/ai-quality/run?target=all")
        assert denied.status_code == 401
        response = client.post("/api/ai-quality/run?target=all", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["target_count"] == 2
        assert body["target_gate_passes"] == 2
        quality = client.get("/api/ai-quality").json()
        assert set(quality["targets"]) == {"evidenceflow", "quotesense"}


def test_unknown_replay_target_is_rejected(monkeypatch):
    monkeypatch.setattr(auth, "HUB_API_KEY", "operator-test-token")
    with TestClient(app) as client:
        response = client.post(
            "/api/ai-quality/run?target=legacylens",
            headers={"Authorization": "Bearer operator-test-token"},
        )
        assert response.status_code == 404


def test_dashboard_does_not_request_provider_credentials():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "No provider key required" in response.text
        assert "HUB_API_KEY" not in response.text
