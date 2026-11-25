from __future__ import annotations

import uuid
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from . import config
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .auth import require_hub_api_key, require_project_ingest_token
from .rate_limit import rate_limiter
from .db import init_db, insert_application_event, query_application_events, quality_metrics
from evals.project_runner import TARGETS, run_all, run_target

init_db()


class ApplicationEvent(BaseModel):
    """Bounded, privacy-safe metadata from the two connected applications."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex, min_length=8, max_length=64)
    project: Literal["evidenceflow", "quotesense"]
    event_type: Literal[
        "run.completed",
        "run.failed",
        "evaluation.completed",
        "ingestion.completed",
        "ingestion.failed",
    ]
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
        "Internal quality evaluation and read-only observability for EvidenceFlow and QuoteSense. "
        "Only bounded application metadata is accepted; no user content or provider credentials."
    ),
)


_WRITE_PATHS = {"/api/ai-quality/run", "/api/application-events"}


@app.middleware("http")
async def write_api_ip_rate_limit(request: Request, call_next):
    if request.method == "POST" and request.url.path in _WRITE_PATHS:
        client_ip = request.client.host if request.client is not None else "unknown"
        allowed, retry_after = rate_limiter.check(
            f"write-ip:{client_ip}",
            limit=config.HUB_IP_RATE_LIMIT_PER_MINUTE,
        )
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Write API rate limit reached. Retry later."},
                headers={"Retry-After": str(retry_after)},
            )
    return await call_next(request)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ai-engineering-evaluation",
        "version": app.version,
    }


@app.get("/ready")
def ready():
    try:
        from .db import db

        with db() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ready", "database": "ok"}
    except Exception as exc:
        raise HTTPException(503, f"not ready: {exc}") from exc


@app.get("/api/ai-quality")
def ai_quality(limit: int = 200):
    data = quality_metrics(limit)
    public_projects = {"evidenceflow", "quotesense"}
    data["targets"] = {
        key: value for key, value in data.get("targets", {}).items()
        if key in public_projects
    }
    data["runs"] = [
        row for row in data.get("runs", [])
        if row.get("target") in public_projects
    ]
    data["target_count"] = len(data["targets"])
    data["target_gate_passes"] = sum(
        1 for item in data["targets"].values() if item.get("passed")
    )
    scores = [float(item.get("score", 0)) for item in data["targets"].values()]
    data["platform_score"] = round(sum(scores) / len(scores), 6) if scores else 0.0
    return data


@app.post("/api/ai-quality/run", dependencies=[Depends(require_hub_api_key)])
def run_replay_evaluation(target: str = "all"):
    if target == "all":
        return run_all("replay")
    if target not in TARGETS:
        raise HTTPException(404, "unknown evaluation target")
    return run_target(target, mode="replay")


@app.post("/api/application-events", status_code=202)
def ingest_application_event(
    payload: ApplicationEvent,
    authorization: str | None = Header(default=None),
):
    require_project_ingest_token(payload.project, authorization)
    inserted = insert_application_event(
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
    return {
        "accepted": True,
        "event_id": payload.event_id,
        "duplicate": not inserted,
    }


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
        durations = [
            float(row["duration_ms"])
            for row in rows
            if row.get("duration_ms") is not None
        ]
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


@app.get("/", response_class=HTMLResponse)
def dashboard():
    html = Path(__file__).with_name("dashboard.html").read_text(encoding="utf-8")
    return HTMLResponse(html)
