import uuid

from fastapi.testclient import TestClient

from app import auth
from app.main import app


def test_mlops_registry_and_dataset_sync_are_visible():
    with TestClient(app) as client:
        overview = client.get("/api/mlops/overview")
        assert overview.status_code == 200
        body = overview.json()
        assert body["dataset_registry"]["count"] >= 1
        assert body["runtime_model"]["status"] == "observed"

        datasets = client.get("/api/mlops/datasets").json()
        assert any(item["name"] == "evidenceflow" for item in datasets)
        assert all(len(item["content_hash"]) == 64 for item in datasets)


def test_quality_run_is_tracked_as_experiment():
    with TestClient(app) as client:
        response = client.post("/api/ai-quality/run?target=evidenceflow")
        assert response.status_code == 200
        batch = response.json()
        assert batch["experiment_id"]
        experiments = client.get("/api/mlops/experiments?limit=20").json()
        row = next(item for item in experiments if item["id"] == batch["experiment_id"])
        assert row["status"] == "completed"
        assert row["dataset_name"] == "evidenceflow"
        assert row["dataset_version"] == "v1"


def test_model_promotion_gate():
    name = f"portfolio-model-{uuid.uuid4().hex[:8]}"
    with TestClient(app) as client:
        created = client.post("/api/mlops/models", json={
            "name": name,
            "provider": "test-provider",
            "version": "v2",
            "status": "candidate",
            "eval_score": 0.95,
            "eval_dataset_version": "v1",
        })
        assert created.status_code == 200
        model_id = created.json()["id"]

        promoted = client.post(f"/api/mlops/models/{model_id}/promote", json={"min_score": 0.90})
        assert promoted.status_code == 200
        assert promoted.json()["status"] == "production"


def test_mutating_mlops_api_requires_bearer_key_when_configured(monkeypatch):
    monkeypatch.setattr(auth, "HUB_API_KEY", "test-secret")
    with TestClient(app) as client:
        missing = client.post("/api/mlops/models", json={"name": "x", "provider": "y", "version": "z"})
        assert missing.status_code == 401
        invalid = client.post("/api/mlops/models", headers={"Authorization": "Bearer wrong"}, json={"name": "x", "provider": "y", "version": "z"})
        assert invalid.status_code == 401
        valid = client.post("/api/mlops/models", headers={"Authorization": "Bearer test-secret"}, json={"name": "x", "provider": "y", "version": "z"})
        assert valid.status_code == 200
