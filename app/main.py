from __future__ import annotations

import uuid
from pathlib import Path
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .auth import require_hub_api_key, require_project_ingest_token
from .db import (
    create_approval, db, decide_approval, init_db, insert_application_event,
    insert_audit, insert_config, insert_experiment_comparison, metrics,
    query_application_events, query_configs, query_experiments, query_rows,
    query_traces, quality_metrics,
)
from evals.experiments import compare_batches

init_db()


class ApplicationEvent(BaseModel):
    """Small, privacy-safe event contract for project-owned app telemetry."""
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex, min_length=8, max_length=64)
    project: Literal["evidenceflow", "quotesense"]
    event_type: Literal["run.completed", "run.failed", "evaluation.completed", "ingestion.completed", "ingestion.failed"]
    status: Literal["success", "warning", "failed"]
    workflow: str = Field(min_length=1, max_length=80)
    duration_ms: float | None = Field(default=None, ge=0, le=900000)
    model: str | None = Field(default=None, max_length=120)
    request_id: str | None = Field(default=None, max_length=100)
    metrics: dict[str, float | int | bool] = Field(default_factory=dict)

    @field_validator("metrics")
    @classmethod
    def validate_metrics(cls, value: dict[str, float | int | bool]) -> dict[str, float | int | bool]:
        if len(value) > 24:
            raise ValueError("at most 24 numeric metrics may be recorded")
        for key, metric in value.items():
            if not key or len(key) > 48 or not all(ch.isalnum() or ch in "_@.-" for ch in key):
                raise ValueError("metric names must be short identifiers")
            if isinstance(metric, float) and (metric != metric or abs(metric) == float("inf")):
                raise ValueError("metric values must be finite")
        return value


app = FastAPI(
    title="AI Engineering Evaluation Service",
    version="4.0.0",
    description=(
        "Internal evaluation and observability service for EvidenceFlow and QuoteSense. "
        "Project services send bounded, non-content telemetry; the dashboard is read-only."
    ),
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-engineering-automation-llmops-platform", "version": app.version}


@app.get("/ready")
def ready():
    try:
        with db() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ready", "database": "ok"}
    except Exception as exc:
        raise HTTPException(503, f"not ready: {exc}") from exc


@app.get("/api/metrics")
def metrics_api():
    return metrics()


@app.get("/api/llm-runs")
def llm_runs(limit: int = 50):
    return query_rows("llm_runs", limit)


@app.get("/api/evaluations")
def evaluations(limit: int = 50):
    return query_rows("evaluation_runs", limit)


@app.get("/api/ai-quality")
def ai_quality(limit: int = 200):
    return quality_metrics(limit)


@app.post("/api/ai-quality/run", dependencies=[Depends(require_hub_api_key)])
def ai_quality_run(target: str = "all"):
    from evals.project_runner import TARGETS, run_all, run_target
    if target == "all":
        return run_all("replay")
    if target not in TARGETS:
        raise HTTPException(404, f"unknown target: {target}")
    return run_target(target, mode="replay")


@app.get("/api/traces")
def traces(limit: int = 100, run_id: Optional[str] = None):
    return query_traces(limit, run_id)


@app.get("/api/config-registry")
def config_registry(limit: int = 100):
    return query_configs(limit)


@app.post("/api/config-registry", dependencies=[Depends(require_hub_api_key)])
def config_registry_create(payload: dict):
    component = str(payload.get("component") or "").strip()
    version = str(payload.get("version") or "").strip()
    if not component or not version:
        raise HTTPException(400, "component and version are required")
    config_id = insert_config(component=component, version=version, config=payload.get("config", {}), notes=str(payload.get("notes", "")), active=bool(payload.get("active", True)))
    return {"id": config_id, "component": component, "version": version}


@app.get("/api/experiments")
def experiments(limit: int = 100):
    return query_experiments(limit)


@app.post("/api/experiments/compare", dependencies=[Depends(require_hub_api_key)])
def experiments_compare(payload: dict):
    target = str(payload.get("target") or "").strip().lower()
    baseline_batch_id = str(payload.get("baseline_batch_id") or "").strip()
    candidate_batch_id = str(payload.get("candidate_batch_id") or "").strip()
    experiment_id = str(payload.get("experiment_id") or uuid.uuid4()) if payload.get("experiment_id") else str(uuid.uuid4())
    if not target or not baseline_batch_id or not candidate_batch_id:
        raise HTTPException(400, "target, baseline_batch_id and candidate_batch_id are required")
    try:
        comparison = compare_batches(target=target, baseline_batch_id=baseline_batch_id, candidate_batch_id=candidate_batch_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    comparison_id = insert_experiment_comparison(experiment_id=experiment_id, target=target, baseline_batch_id=baseline_batch_id, candidate_batch_id=candidate_batch_id, comparison=comparison)
    comparison["comparison_id"] = comparison_id
    comparison["experiment_id"] = experiment_id
    insert_audit("experiment_comparison", "passed" if comparison["passed"] else "regression", comparison, actor="experiment-engine")
    return comparison


@app.get("/api/experiments/latest")
def experiments_latest():
    quality = quality_metrics(2000)
    targets = {}
    for slug, item in quality.get("targets", {}).items():
        # Derive a full latest-vs-previous comparison when two batches exist.
        runs = [row for row in quality.get("runs", []) if row.get("target") == slug]
        batches = []
        for row in runs:
            if row["batch_id"] not in batches:
                batches.append(row["batch_id"])
        if len(batches) >= 2:
            try:
                targets[slug] = compare_batches(target=slug, baseline_batch_id=batches[1], candidate_batch_id=batches[0])
            except KeyError:
                targets[slug] = {"target": slug, "status": "unavailable"}
        else:
            targets[slug] = {"target": slug, "status": "first_run", "score": item.get("score")}
    return {"targets": targets}


@app.post("/api/application-events", status_code=202)
def ingest_application_event(
    payload: ApplicationEvent,
    authorization: str | None = Header(default=None),
):
    require_project_ingest_token(payload.project, authorization)
    stored = insert_application_event(
        event_id=payload.event_id,
        project=payload.project,
        event_type=payload.event_type,
        status=payload.status,
        workflow=payload.workflow,
        duration_ms=payload.duration_ms,
        model=payload.model,
        request_id=payload.request_id,
        metrics=payload.metrics,
    )
    return {"accepted": True, "event_id": payload.event_id, "duplicate": not stored}


@app.get("/api/application-events")
def application_events(project: str | None = None, limit: int = 60):
    if project is not None and project not in {"evidenceflow", "quotesense"}:
        raise HTTPException(400, "project must be evidenceflow or quotesense")
    return query_application_events(limit=limit, project=project)


@app.get("/api/application-summary")
def application_summary():
    events = query_application_events(limit=1000)
    summary = {}
    for project in ("evidenceflow", "quotesense"):
        rows = [row for row in events if row["project"] == project]
        durations = [float(row["duration_ms"]) for row in rows if row.get("duration_ms") is not None]
        summary[project] = {
            "events": len(rows),
            "successful": sum(row["status"] == "success" for row in rows),
            "warnings": sum(row["status"] == "warning" for row in rows),
            "failed": sum(row["status"] == "failed" for row in rows),
            "average_duration_ms": round(sum(durations) / len(durations), 2) if durations else None,
            "last_event_at": rows[0]["created_at"] if rows else None,
            "last_status": rows[0]["status"] if rows else "no activity",
        }
    return {"projects": summary, "total_events": len(events)}


@app.get("/api/audit")
def audit_events(limit: int = 50):
    return query_rows("audit_events", limit)


@app.get("/api/approvals")
def approvals(status: Optional[str] = None, limit: int = 50):
    with db() as conn:
        if status:
            rows = conn.execute("SELECT * FROM approvals WHERE status=? ORDER BY created_at DESC LIMIT ?", (status, max(1, min(limit, 200)))).fetchall()
        else:
            rows = conn.execute("SELECT * FROM approvals ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 200)),)).fetchall()
    return [dict(row) for row in rows]


@app.post("/approvals", dependencies=[Depends(require_hub_api_key)])
def approval_create(req: ApprovalRequest):
    result = create_approval(req.workflow, req.summary, req.payload)
    insert_audit("approval_created", "pending", {**result, "workflow": req.workflow})
    return result


@app.post("/approvals/{approval_id}/decision", dependencies=[Depends(require_hub_api_key)])
def approval_decision(approval_id: str, req: DecisionRequest):
    try:
        result = decide_approval(approval_id, req.status, req.decided_by, req.decision_note)
    except KeyError as exc:
        raise HTTPException(404, "approval not found") from exc
    insert_audit("approval_decision", req.status, {**result}, actor=req.decided_by)
    return result


@app.get("/", response_class=HTMLResponse)
def dashboard():
    html = Path(__file__).with_name("dashboard.html").read_text()
    return HTMLResponse(html)
