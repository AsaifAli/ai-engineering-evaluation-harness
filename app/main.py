from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .gateway import GatewayError, chat_json, gateway_configured

APP_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("AUDIT_DB", str(APP_DIR.parent / "data" / "audit.db")))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="AI Engineering Automation Hub",
    version="2.0.0",
    description="AI-assisted engineering automation services designed to be orchestrated by n8n."
)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS audit_events (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            status TEXT NOT NULL,
            actor TEXT,
            payload TEXT NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS approvals (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL,
            workflow TEXT NOT NULL,
            summary TEXT NOT NULL,
            payload TEXT NOT NULL,
            decided_at TEXT,
            decided_by TEXT,
            decision_note TEXT
        )""")


init_db()


class IssueRequest(BaseModel):
    title: str
    body: str = ""
    labels: List[str] = Field(default_factory=list)
    repository: Optional[str] = None
    author: Optional[str] = None


class PRRequest(BaseModel):
    title: str
    body: str = ""
    changed_files: int = 0
    additions: int = 0
    deletions: int = 0
    repository: Optional[str] = None
    author: Optional[str] = None
    diff: Optional[str] = None


class ExperimentRequest(BaseModel):
    experiment: str
    metrics: Dict[str, Any]
    baseline: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ApprovalRequest(BaseModel):
    workflow: str
    summary: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class DecisionRequest(BaseModel):
    status: str
    decided_by: str = "human"
    decision_note: str = ""


def audit(event_type: str, status: str, payload: Dict[str, Any], actor: str = "system"):
    event_id = str(uuid.uuid4())
    with db() as conn:
        conn.execute(
            "INSERT INTO audit_events VALUES (?, ?, ?, ?, ?, ?)",
            (event_id, datetime.now(timezone.utc).isoformat(), event_type, status, actor, json.dumps(payload))
        )
    return event_id


def heuristic_triage(req: IssueRequest) -> Dict[str, Any]:
    text = f"{req.title} {req.body}".lower()
    security_terms = ["security", "credential", "secret", "token leaked", "vulnerability", "cve", "exploit"]
    bug_terms = ["bug", "error", "exception", "crash", "failed", "failure", "broken", "regression"]
    ml_terms = ["model", "training", "inference", "embedding", "rag", "llm", "agent", "vector"]
    security = any(x in text for x in security_terms)
    bug = any(x in text for x in bug_terms)
    ml = any(x in text for x in ml_terms)
    priority = "critical" if security and any(x in text for x in ["leaked", "exploit", "production"]) else "high" if security or bug else "medium" if ml else "low"
    category = "security" if security else "bug" if bug else "ai-ml" if ml else "engineering"
    labels = [f"ai:{category}", f"priority:{priority}"]
    return {
        "category": category,
        "priority": priority,
        "labels": labels,
        "summary": req.title[:160],
        "recommended_action": (
            "Escalate for immediate security review and rotate affected credentials if exposure is confirmed."
            if security else
            "Assign an engineering owner, reproduce the issue, and review within the normal SLA."
            if bug else
            "Route to the AI/ML owner and review model, data, or retrieval context before changing production behavior."
            if ml else
            "Assign an engineering owner and triage against the normal backlog SLA."
        ),
        "confidence": 0.88 if security or bug else 0.76,
        "requires_human_approval": True,
        "model": "deterministic-fallback-v1"
    }


def pr_risk(req: PRRequest) -> Dict[str, Any]:
    text = f"{req.title} {req.body} {req.diff or ''}".lower()
    security = any(x in text for x in ["auth", "secret", "credential", "permission", "token"])
    infra = any(x in text for x in ["docker", "terraform", "deploy", "migration", "database"])
    size_score = req.changed_files * 1.5 + req.additions / 100 + req.deletions / 150
    risk = "high" if security or size_score >= 45 else "medium" if infra or size_score >= 18 else "low"
    checks = ["tests and regression coverage", "error handling and observability", "configuration/secrets hygiene"]
    if security: checks.insert(0, "authentication/authorization and secret exposure")
    if infra: checks.append("deployment, migration and rollback safety")
    return {
        "risk": risk,
        "risk_score": round(min(100, size_score + (30 if security else 0) + (15 if infra else 0)), 1),
        "review_summary": req.title[:180],
        "recommended_checks": checks,
        "requires_human_approval": True,
        "model": "deterministic-fallback-v1"
    }


LOWER_IS_BETTER_METRICS = {
    "latency",
    "latency_ms",
    "response_time",
    "response_time_ms",
    "inference_time",
    "inference_time_ms",
    "duration",
    "duration_ms",
    "loss",
    "error",
    "error_rate",
    "cost",
    "cost_usd",
    "memory_mb",
    "memory_gb",
}


def experiment_report(req: ExperimentRequest) -> Dict[str, Any]:
    deltas = {}
    for key, value in req.metrics.items():
        base = req.baseline.get(key)
        if isinstance(value, (int, float)) and isinstance(base, (int, float)) and base != 0:
            deltas[key] = round((value - base) / abs(base) * 100, 2)

    # Most model-quality metrics improve when they increase (e.g. recall,
    # precision, NDCG). Operational metrics such as latency, error rate,
    # loss, and cost improve when they decrease.
    regressions = []
    improvements = []
    for key, delta in deltas.items():
        lower_is_better = key.lower() in LOWER_IS_BETTER_METRICS
        if lower_is_better:
            if delta > 2:
                regressions.append(key)
            elif delta < -2:
                improvements.append(key)
        else:
            if delta < -2:
                regressions.append(key)
            elif delta > 2:
                improvements.append(key)

    return {
        "experiment": req.experiment,
        "metrics": req.metrics,
        "baseline": req.baseline,
        "relative_deltas_pct": deltas,
        "regressions": regressions,
        "improvements": improvements,
        "summary": f"Compared {len(deltas)} metrics against baseline; {len(regressions)} potential regressions and {len(improvements)} meaningful improvements detected.",
        "next_action": "Review regressions and approve the generated engineering digest before distribution." if regressions else "Review the experiment summary and approve distribution.",
        "requires_human_approval": True,
        "model": "deterministic-fallback-v1"
    }



def gateway_enabled() -> bool:
    return os.getenv("LLM_PROVIDER", "deterministic").lower() == "gateway" and gateway_configured()


async def gateway_triage(req: IssueRequest) -> Dict[str, Any]:
    system = """You are an AI engineering issue triage assistant.
Return ONLY valid JSON with these keys:
category, priority, labels, summary, recommended_action, confidence, requires_human_approval.

Allowed category values: security, bug, ai-ml, engineering.
Allowed priority values: critical, high, medium, low.
labels must be an array of strings.
confidence must be a number from 0 to 1.
requires_human_approval must always be true.

Be conservative. Security-related issues should receive high or critical priority when justified.
"""

    user = json.dumps({
        "title": req.title,
        "body": req.body,
        "labels": req.labels,
        "repository": req.repository,
        "author": req.author,
    })

    result = await chat_json(
        system_prompt=system,
        user_prompt=f"Classify this GitHub issue:\n{user}",
    )

    category = str(result.get("category", "engineering")).lower()
    priority = str(result.get("priority", "medium")).lower()

    if category not in {"security", "bug", "ai-ml", "engineering"}:
        raise GatewayError("Invalid issue category from gateway")
    if priority not in {"critical", "high", "medium", "low"}:
        raise GatewayError("Invalid issue priority from gateway")

    labels = result.get("labels", [])
    if not isinstance(labels, list):
        raise GatewayError("Invalid issue labels from gateway")

    try:
        confidence = float(result.get("confidence", 0.7))
    except (TypeError, ValueError):
        raise GatewayError("Invalid issue confidence from gateway")

    confidence = max(0.0, min(1.0, confidence))

    return {
        "category": category,
        "priority": priority,
        "labels": [str(x) for x in labels],
        "summary": str(result.get("summary", req.title[:160]))[:160],
        "recommended_action": str(
            result.get(
                "recommended_action",
                "Assign an engineering owner and review the issue."
            )
        ),
        "confidence": confidence,
        "requires_human_approval": True,
        "model": os.getenv("GATEWAY_MODEL") or "gateway-selected-model",
        "ai_source": "gateway",
    }


async def gateway_pr_review(req: PRRequest) -> Dict[str, Any]:
    system = """You are an AI engineering PR review assistant.
Return ONLY valid JSON with these keys:
risk, risk_score, review_summary, recommended_checks, requires_human_approval.

Allowed risk values: high, medium, low.
risk_score must be a number from 0 to 100.
recommended_checks must be an array of strings.
requires_human_approval must always be true.

Assess engineering risk from the PR metadata and diff. Pay particular attention
to security, infrastructure, deployment, migrations, authentication, secrets,
and large changes.
"""

    user = json.dumps({
        "title": req.title,
        "body": req.body,
        "changed_files": req.changed_files,
        "additions": req.additions,
        "deletions": req.deletions,
        "repository": req.repository,
        "author": req.author,
        "diff": req.diff,
    })

    result = await chat_json(
        system_prompt=system,
        user_prompt=f"Assess this pull request:\n{user}",
    )

    risk = str(result.get("risk", "medium")).lower()
    if risk not in {"high", "medium", "low"}:
        raise GatewayError("Invalid PR risk from gateway")

    try:
        risk_score = float(result.get("risk_score", 50))
    except (TypeError, ValueError):
        raise GatewayError("Invalid PR risk_score from gateway")

    checks = result.get("recommended_checks", [])
    if not isinstance(checks, list):
        raise GatewayError("Invalid PR recommended_checks from gateway")

    return {
        "risk": risk,
        "risk_score": round(max(0.0, min(100.0, risk_score)), 1),
        "review_summary": str(result.get("review_summary", req.title[:180]))[:180],
        "recommended_checks": [str(x) for x in checks],
        "requires_human_approval": True,
        "model": os.getenv("GATEWAY_MODEL") or "gateway-selected-model",
        "ai_source": "gateway",
    }


async def gateway_experiment_summary(req: ExperimentRequest) -> Dict[str, Any]:
    # Keep the numerical comparison deterministic. Use the LLM for engineering
    # interpretation and communication of the already-computed findings.
    baseline_result = experiment_report(req)

    system = """You are an AI engineering experiment reporting assistant.
Return ONLY valid JSON with these keys:
summary, next_action.

Do not invent metrics or change the supplied regression/improvement findings.
Write a concise engineering-oriented summary and a practical next action.
"""

    user = json.dumps({
        "experiment": req.experiment,
        "metrics": req.metrics,
        "baseline": req.baseline,
        "relative_deltas_pct": baseline_result["relative_deltas_pct"],
        "regressions": baseline_result["regressions"],
        "improvements": baseline_result["improvements"],
        "metadata": req.metadata,
    })

    result = await chat_json(
        system_prompt=system,
        user_prompt=f"Summarize these experiment results:\n{user}",
    )

    return {
        **baseline_result,
        "summary": str(result.get("summary", baseline_result["summary"])),
        "next_action": str(result.get("next_action", baseline_result["next_action"])),
        "model": os.getenv("GATEWAY_MODEL") or "gateway-selected-model",
        "ai_source": "gateway",
    }


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-engineering-automation-hub", "version": app.version}


@app.get("/api/audit")
def audit_events(limit: int = 50):
    limit = max(1, min(limit, 200))
    with db() as conn:
        rows = conn.execute("SELECT * FROM audit_events ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/approvals")
def approvals(status: Optional[str] = None):
    with db() as conn:
        if status:
            rows = conn.execute("SELECT * FROM approvals WHERE status=? ORDER BY created_at DESC", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM approvals ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


@app.post("/ai/triage")
async def triage(req: IssueRequest):
    fallback_reason = None

    if gateway_enabled():
        try:
            result = await gateway_triage(req)
        except Exception as exc:
            result = heuristic_triage(req)
            result["ai_source"] = "deterministic-fallback"
            fallback_reason = str(exc)
    else:
        result = heuristic_triage(req)
        result["ai_source"] = "deterministic-fallback"

    if fallback_reason:
        result["fallback_reason"] = fallback_reason

    event_id = audit(
        "issue_triage",
        "completed",
        {"request": req.model_dump(), "result": result},
    )
    result["audit_event_id"] = event_id
    return result


@app.post("/ai/pr-review")
async def pr_review(req: PRRequest):
    fallback_reason = None

    if gateway_enabled():
        try:
            result = await gateway_pr_review(req)
        except Exception as exc:
            result = pr_risk(req)
            result["ai_source"] = "deterministic-fallback"
            fallback_reason = str(exc)
    else:
        result = pr_risk(req)
        result["ai_source"] = "deterministic-fallback"

    if fallback_reason:
        result["fallback_reason"] = fallback_reason

    event_id = audit(
        "pr_review",
        "completed",
        {"request": req.model_dump(), "result": result},
    )
    result["audit_event_id"] = event_id
    return result


@app.post("/ai/experiment-summary")
async def experiment_summary(req: ExperimentRequest):
    fallback_reason = None

    if gateway_enabled():
        try:
            result = await gateway_experiment_summary(req)
        except Exception as exc:
            result = experiment_report(req)
            result["ai_source"] = "deterministic-fallback"
            fallback_reason = str(exc)
    else:
        result = experiment_report(req)
        result["ai_source"] = "deterministic-fallback"

    if fallback_reason:
        result["fallback_reason"] = fallback_reason

    event_id = audit(
        "experiment_summary",
        "completed",
        {"request": req.model_dump(), "result": result},
    )
    result["audit_event_id"] = event_id
    return result


@app.post("/approvals")
def create_approval(req: ApprovalRequest):
    approval_id = str(uuid.uuid4())
    with db() as conn:
        conn.execute(
            "INSERT INTO approvals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (approval_id, datetime.now(timezone.utc).isoformat(), "pending", req.workflow,
             req.summary, json.dumps(req.payload), None, None, None)
        )
    audit("approval_created", "pending", {"approval_id": approval_id, "workflow": req.workflow})
    return {"approval_id": approval_id, "status": "pending"}


@app.post("/approvals/{approval_id}/decision")
def decide_approval(approval_id: str, req: DecisionRequest):
    if req.status not in {"approved", "rejected"}:
        raise HTTPException(400, "status must be approved or rejected")
    with db() as conn:
        row = conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
        if not row:
            raise HTTPException(404, "approval not found")
        conn.execute(
            "UPDATE approvals SET status=?, decided_at=?, decided_by=?, decision_note=? WHERE id=?",
            (req.status, datetime.now(timezone.utc).isoformat(), req.decided_by, req.decision_note, approval_id)
        )
    audit("approval_decision", req.status, {"approval_id": approval_id, "note": req.decision_note}, req.decided_by)
    return {"approval_id": approval_id, "status": req.status}


@app.post("/webhooks/n8n")
async def n8n_webhook(request: Request):
    payload = await request.json()
    event_id = audit("n8n_webhook", "received", payload, "n8n")
    return {"received": True, "audit_event_id": event_id}


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse("""<!doctype html>
<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>AI Engineering Automation Hub</title><style>
body{font-family:system-ui,-apple-system,sans-serif;max-width:1100px;margin:40px auto;padding:0 20px;background:#f7f7f7;color:#222}h1{margin-bottom:6px}.sub{color:#666}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:24px 0}.card{background:white;border:1px solid #ddd;border-radius:12px;padding:18px}.metric{font-size:28px;font-weight:700}table{width:100%;border-collapse:collapse;background:white}td,th{padding:10px;border-bottom:1px solid #eee;text-align:left;font-size:14px}code{background:#eee;padding:2px 5px;border-radius:4px}@media(max-width:700px){.grid{grid-template-columns:1fr}}
</style></head><body><h1>AI Engineering Automation Hub</h1><div class='sub'>n8n orchestration + FastAPI AI services + human approval + audit trail</div>
<div class='grid'><div class='card'><div>Service</div><div class='metric'>Online</div></div><div class='card'><div>AI Workflows</div><div class='metric'>3</div></div><div class='card'><div>Audit Events</div><div class='metric' id='count'>—</div></div></div>
<h2>Recent audit events</h2><table><thead><tr><th>Time</th><th>Event</th><th>Status</th><th>Actor</th></tr></thead><tbody id='events'></tbody></table>
<script>fetch('/api/audit').then(r=>r.json()).then(rows=>{document.getElementById('count').textContent=rows.length;document.getElementById('events').innerHTML=rows.map(x=>`<tr><td>${x.created_at}</td><td>${x.event_type}</td><td>${x.status}</td><td>${x.actor||''}</td></tr>`).join('')})</script>
</body></html>""")
