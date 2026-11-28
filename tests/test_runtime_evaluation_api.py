from fastapi.testclient import TestClient

from app import auth, config
from app.main import app
import app.main as main_module


def test_application_event_accepts_optional_experiment_lineage(monkeypatch):
    monkeypatch.setattr(
        config,
        "HARNESS_INGEST_TOKENS_JSON",
        '{"evidenceflow":"evidence-token"}',
    )
    inserted = {}

    def capture(**kwargs):
        inserted.update(kwargs)
        return True

    monkeypatch.setattr(main_module, "insert_application_event", capture)
    payload = {
        "event_id": "ef-" + "x" * 32,
        "project": "evidenceflow",
        "event_type": "evaluation.completed",
        "status": "success",
        "workflow": "rag_query",
        "model": "provider/model",
        "experiment_id": "ragas-exp-2026-11",
        "dataset_version": "support-v2",
        "prompt_version": "synthesis-v4",
        "model_version": "model-2026-11",
        "config_version": "retrieval-v3",
        "metrics": {
            "external.ragas.faithfulness": 0.94,
            "external.ragas.answer_relevancy": 0.91,
        },
    }

    with TestClient(app) as client:
        response = client.post(
            "/api/application-events",
            headers={"Authorization": "Bearer evidence-token"},
            json=payload,
        )

    assert response.status_code == 202
    assert inserted["experiment_id"] == "ragas-exp-2026-11"
    assert inserted["dataset_version"] == "support-v2"
    assert inserted["prompt_version"] == "synthesis-v4"
    assert inserted["model_version"] == "model-2026-11"
    assert inserted["config_version"] == "retrieval-v3"


def test_application_event_lineage_fields_are_bounded_and_strict():
    payload = {
        "event_id": "ef-" + "y" * 32,
        "project": "evidenceflow",
        "event_type": "evaluation.completed",
        "status": "success",
        "workflow": "rag_query",
        "experiment_id": "x" * 129,
        "metrics": {"external.ragas.faithfulness": 0.9},
    }
    with TestClient(app) as client:
        response = client.post(
            "/api/application-events",
            headers={"Authorization": "Bearer any-token"},
            json=payload,
        )
    assert response.status_code == 422


def test_runtime_evaluations_api_returns_only_evaluation_events_and_aggregates(monkeypatch):
    events = [
        {
            "id": "1",
            "created_at": "2026-11-28T10:00:00+00:00",
            "project": "evidenceflow",
            "event_type": "evaluation.completed",
            "status": "success",
            "workflow": "rag_query",
            "model": "provider/model",
            "experiment_id": "baseline",
            "dataset_version": "dataset-v1",
            "prompt_version": "prompt-v1",
            "model_version": "model-v1",
            "config_version": "config-v1",
            "metrics": {"external.ragas.faithfulness": 0.9},
        },
        {
            "id": "2",
            "created_at": "2026-11-28T10:01:00+00:00",
            "project": "evidenceflow",
            "event_type": "run.completed",
            "status": "success",
            "workflow": "rag_query",
            "metrics": {"retrieved_chunks": 3},
        },
        {
            "id": "3",
            "created_at": "2026-11-28T10:02:00+00:00",
            "project": "evidenceflow",
            "event_type": "evaluation.completed",
            "status": "success",
            "workflow": "rag_query",
            "experiment_id": "candidate",
            "metrics": {"external.ragas.faithfulness": 0.8},
        },
    ]
    monkeypatch.setattr(main_module, "query_application_events", lambda limit, project=None: events)

    with TestClient(app) as client:
        response = client.get("/api/ai-quality/runtime?project=evidenceflow")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert len(body["results"]) == 2
    assert body["summary"]["external.ragas.faithfulness"]["mean"] == 0.85
    assert "prompt_text" not in str(body).lower()\n    assert "answer_text" not in str(body).lower()
    assert all(item["event_type"] == "evaluation.completed" for item in body["results"])


def test_runtime_experiment_comparison_uses_runtime_metric_deltas(monkeypatch):
    events = [
        {
            "created_at": "2026-11-28T10:00:00+00:00",
            "project": "evidenceflow",
            "event_type": "evaluation.completed",
            "status": "success",
            "experiment_id": "baseline",
            "model_version": "model-a",
            "prompt_version": "prompt-a",
            "dataset_version": "dataset-a",
            "config_version": "config-a",
            "metrics": {
                "external.ragas.faithfulness": 0.95,
                "external.ragas.answer_relevancy": 0.9,
            },
        },
        {
            "created_at": "2026-11-28T10:01:00+00:00",
            "project": "evidenceflow",
            "event_type": "evaluation.completed",
            "status": "success",
            "experiment_id": "candidate",
            "model_version": "model-b",
            "prompt_version": "prompt-b",
            "dataset_version": "dataset-a",
            "config_version": "config-b",
            "metrics": {
                "external.ragas.faithfulness": 0.7,
                "external.ragas.answer_relevancy": 0.93,
            },
        },
    ]
    monkeypatch.setattr(main_module, "query_application_events", lambda limit, project=None: events)

    with TestClient(app) as client:
        response = client.get(
            "/api/ai-quality/runtime-experiments"
            "?target=evidenceflow&baseline_experiment_id=baseline"
        )

    assert response.status_code == 200
    candidate = next(
        item for item in response.json()["experiments"]
        if item["experiment_id"] == "candidate"
    )
    assert candidate["metric_deltas"]["external.ragas.faithfulness"] == -0.25
    assert candidate["metric_deltas"]["external.ragas.answer_relevancy"] == 0.03
    assert candidate["regression_detected"] is True
