from fastapi.testclient import TestClient

from app import auth
from app.main import app
import app.main as main_module


def test_health_and_readiness():
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        ready = client.get("/ready")
        assert ready.status_code == 200
        assert ready.json()["database"] == "ok"


def test_replay_evaluation_covers_the_three_connected_apps(monkeypatch):
    monkeypatch.setattr(auth, "HUB_API_KEY", "operator-test-token")
    headers = {"Authorization": "Bearer operator-test-token"}
    with TestClient(app) as client:
        denied = client.post("/api/ai-quality/run?target=all")
        assert denied.status_code == 401
        response = client.post("/api/ai-quality/run?target=all", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["target_count"] == 3
        assert body["target_gate_passes"] == 3
        quality = client.get("/api/ai-quality").json()
        assert set(quality["targets"]) == {"evidenceflow", "quotesense", "flowpilot"}


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



def test_public_quality_api_hides_retired_project_history(monkeypatch):
    monkeypatch.setattr(
        main_module,
        "quality_metrics",
        lambda limit: {
            "targets": {
                "evidenceflow": {"score": 0.9, "passed": True},
                "quotesense": {"score": 0.95, "passed": True},
                "flowpilot": {"score": 0.93, "passed": True},
                "legacylens": {"score": 0.8, "passed": False},
            },
            "runs": [
                {"target": "evidenceflow"},
                {"target": "quotesense"},
                {"target": "flowpilot"},
                {"target": "legacylens"},
            ],
            "target_count": 3,
            "target_gate_passes": 2,
            "platform_score": 0.88,
        },
    )
    with TestClient(app) as client:
        response = client.get("/api/ai-quality")
    body = response.json()
    assert set(body["targets"]) == {"evidenceflow", "quotesense"}
    assert {row["target"] for row in body["runs"]} == {"evidenceflow", "quotesense"}
    assert body["target_count"] == 2
    assert body["target_gate_passes"] == 2

def test_dashboard_keeps_read_only_data_sources_independent():
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Promise.allSettled" in response.text
    assert "Replay evaluation results are temporarily unavailable." in response.text
    assert "Application summary temporarily unavailable" in response.text
    assert "HUB_API_KEY" not in response.text
    assert "No provider key required" in response.text
