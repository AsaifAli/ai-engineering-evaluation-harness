from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from . import gateway
from . import config
from .auth import require_hub_api_key
from .mlops import complete_experiment, create_experiment, ensure_runtime_model, overview as mlops_overview, promote_model, sync_builtin_datasets
from .db import create_approval, db, decide_approval, init_db, insert_audit, insert_config, insert_experiment_comparison, insert_trace, metrics, query_configs, query_experiments, query_judges, query_rows, query_traces, quality_metrics, query_models, query_datasets, query_experiments_runs, insert_model
from .models import ApprovalRequest, DecisionRequest, ExperimentRequest, IssueRequest, PRRequest
from .services import run_experiment_summary, run_issue_triage, run_pr_review
from .targets import check_all_target_health, target_catalog, target_registry
from .adapters.registry import live_adapter, replay_adapter, registered_adapter_plugins
from evals.registry import pack_catalog
from evals.experiments import compare_batches
from evals.judge import judge_response
from .harness import AdapterError, timed_run

init_db()
sync_builtin_datasets("v1")
ensure_runtime_model()

for _component, _version, _config in (
    ("harness", config.HARNESS_CONFIG_VERSION, {"architecture": "modular", "public_mode": "replay_safe"}),
    ("llm-judge", "v1", {"provider": "shared-gateway", "criteria": ["answer_relevance", "groundedness", "completeness", "faithfulness", "overall"]}),
    ("ci-quality-gate", "v1", {"baseline": "evals/baselines/replay_v1.json", "max_regression": 0.02}),
):
    if not any(row["component"] == _component and row["version"] == _version for row in query_configs(500)):
        insert_config(component=_component, version=_version, config=_config, notes="Built-in platform configuration", active=True)

app = FastAPI(
    title="AI Engineering Automation & LLMOps Platform",
    version="3.1.0",
    description=("Event-driven AI engineering automation with n8n orchestration, shared LLM gateway, "
                 "guardrails, evaluations, observability, human approval and auditability."),
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "ai-engineering-automation-llmops-platform", "version": app.version}


@app.get("/ready")
def ready():
    try:
        with db() as conn:
            conn.execute("SELECT 1").fetchone()
        return {"status": "ready", "database": "ok", "gateway": gateway.status()}
    except Exception as exc:
        raise HTTPException(503, f"not ready: {exc}") from exc


@app.get("/api/gateway/status")
def gateway_status():
    return gateway.status()


@app.get("/api/integrations")
def integrations():
    return {
        "gateway": {
            "base_url": config.GATEWAY_BASE_URL,
            "configured": gateway.status().get("configured", False),
        },
        "targets": target_registry(),
        "catalog": target_catalog(),
    }


@app.get("/api/targets/health")
async def target_health():
    return {"targets": await check_all_target_health()}


@app.get("/api/plugins")
def plugins():
    return {
        "adapters": list(registered_adapter_plugins()),
        "evaluation_packs": pack_catalog(),
    }


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


@app.post("/api/ai-quality/run")
def ai_quality_run(target: str = "all"):
    from evals.project_runner import TARGETS, run_all, run_target
    if target == "all":
        return run_all("replay")
    if target not in TARGETS:
        raise HTTPException(404, f"unknown target: {target}")
    return run_target(target, mode="replay")


@app.post("/api/targets/{target}/run", dependencies=[Depends(require_hub_api_key)])
async def run_target_endpoint(target: str, payload: dict, mode: str = "auto"):
    from .targets import TARGETS
    if target not in {spec.slug for spec in TARGETS}:
        raise HTTPException(404, f"unknown target: {target}")
    spec = next(item for item in TARGETS if item.slug == target)
    selected = mode
    if selected == "auto":
        selected = "live" if spec.mode.startswith("live_") else "replay"
    try:
        adapter = live_adapter(target) if selected == "live" else replay_adapter(target)
        result = await timed_run(adapter, str(payload.get("workflow") or "evaluation"), payload)
    except AdapterError as exc:
        raise HTTPException(502, str(exc)) from exc
    trace_steps = result.trace if result.trace is not None else []
    run_metadata = {
        "prompt_version": (result.metadata or {}).get("prompt_version", "target-default-v1"),
        "model_version": (result.metadata or {}).get("model_version", "target-runtime"),
        "config_version": (result.metadata or {}).get("config_version", config.HARNESS_CONFIG_VERSION),
        "integration_mode": spec.mode,
        **(result.metadata or {}),
    }
    trace_id = insert_trace(run_id=result.run_id, target=target, workflow=result.workflow, status=result.status, duration_ms=result.duration_ms, steps=trace_steps, metadata=run_metadata)
    insert_audit("target_run", result.status, {"target": target, "mode": selected, "integration_mode": spec.mode, "result": result.output, "warnings": result.warnings, "trace_id": trace_id, "metadata": result.metadata or {}}, run_id=result.run_id)
    return {
        "target": target,
        "mode": selected,
        "integration_mode": spec.mode,
        "run_id": result.run_id,
        "workflow": result.workflow,
        "status": result.status,
        "duration_ms": result.duration_ms,
        "output": result.output,
        "warnings": result.warnings or [],
        "trace_id": trace_id,
        "metadata": run_metadata,
    }


@app.post("/api/targets/fleet-smoke", dependencies=[Depends(require_hub_api_key)])
async def fleet_smoke(payload: dict | None = None):
    """Run a safe live smoke across the five portfolio targets.

    FlowPilot and LegacyLens retain their existing live adapters. EvidenceFlow,
    QuoteSense and WebQA expose a dedicated /harness/smoke contract so the
    harness can exercise real application code without inventing user workloads.
    """
    payload = payload or {}
    results = []
    for spec in target_catalog():
        slug = spec["slug"]
        if spec["mode"] == "live_smoke":
            run_payload = {"workflow": "harness_smoke", "payload": payload.get(slug, {})}
            try:
                results.append(await run_target_endpoint(slug, run_payload, mode="live"))
            except HTTPException as exc:
                results.append({"target": slug, "integration_mode": spec["mode"], "mode": "live", "status": "failed", "http_status": exc.status_code, "error": str(exc.detail)})
        else:
            # Existing live adapters are already part of the harness; for the
            # fleet smoke we verify their deployment surface without inventing
            # a project-specific business payload.
            results.append({"target": slug, "integration_mode": spec["mode"], "status": "live_adapter_ready", "base_url": spec.get("expected_url")})
    passed = sum(item.get("status") in {"completed", "completed_with_warnings", "success", "live_adapter_ready"} for item in results)
    summary = {"status": "passed" if passed == len(results) else "attention", "targets": results, "passed": passed, "total": len(results)}
    insert_audit("fleet_smoke", summary["status"], summary, actor="n8n")
    return summary


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


@app.get("/api/mlops/overview")
def mlops_summary():
    return mlops_overview()


@app.get("/api/mlops/models")
def mlops_models(limit: int = 100):
    return query_models(limit)


@app.post("/api/mlops/models", dependencies=[Depends(require_hub_api_key)])
def mlops_model_create(payload: dict):
    name = str(payload.get("name") or "").strip()
    provider = str(payload.get("provider") or "").strip()
    version = str(payload.get("version") or "").strip()
    if not name or not provider or not version:
        raise HTTPException(400, "name, provider and version are required")
    status = str(payload.get("status") or "candidate")
    if status not in {"candidate", "observed"}:
        raise HTTPException(400, "new models may only be registered as candidate or observed; use the promotion endpoint for production")
    item = insert_model(
        name=name,
        provider=provider,
        version=version,
        status=status,
        eval_score=float(payload["eval_score"]) if payload.get("eval_score") is not None else None,
        eval_dataset_version=str(payload["eval_dataset_version"]) if payload.get("eval_dataset_version") else None,
        config_version=str(payload.get("config_version") or config.HARNESS_CONFIG_VERSION),
        metadata=payload.get("metadata") or {},
    )
    insert_audit("model_registered", "completed", item, actor="mlops")
    return item


@app.post("/api/mlops/models/{model_id}/promote", dependencies=[Depends(require_hub_api_key)])
def mlops_model_promote(model_id: str, payload: dict | None = None):
    try:
        item = promote_model(model_id, min_score=(payload or {}).get("min_score"))
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    insert_audit("model_promoted", "completed", item, actor="mlops")
    return item


@app.get("/api/mlops/datasets")
def mlops_datasets(limit: int = 200):
    return query_datasets(limit)


@app.post("/api/mlops/datasets/sync", dependencies=[Depends(require_hub_api_key)])
def mlops_datasets_sync(version: str = "v1"):
    items = sync_builtin_datasets(version)
    insert_audit("dataset_registry_sync", "completed", {"version": version, "count": len(items)}, actor="mlops")
    return {"version": version, "count": len(items), "datasets": items}


@app.get("/api/mlops/experiments")
def mlops_experiments(limit: int = 100):
    return query_experiments_runs(limit)


@app.get("/api/judges")
def judges(limit: int = 100):
    return query_judges(limit)


@app.post("/api/judge")
async def judge(payload: dict):
    required = ["target", "case_id", "answer", "reference", "context"]
    missing = [key for key in required if key not in payload]
    if missing:
        raise HTTPException(400, f"missing fields: {', '.join(missing)}")
    return await judge_response(
        target=str(payload["target"]),
        case_id=str(payload["case_id"]),
        answer=str(payload["answer"]),
        reference=str(payload["reference"]),
        context=[str(x) for x in payload.get("context", [])],
        quality_id=str(payload.get("quality_id")) if payload.get("quality_id") else None,
    )


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


@app.post("/ai/triage")
async def triage(req: IssueRequest):
    result = await run_issue_triage(req)
    audit_id = insert_audit("issue_triage", "completed", {"request": req.model_dump(), "result": result}, run_id=result["run_id"])
    result["audit_event_id"] = audit_id
    return result


@app.post("/ai/pr-review")
async def pr_review(req: PRRequest):
    result = await run_pr_review(req)
    audit_id = insert_audit("pr_review", "completed", {"request": req.model_dump(), "result": result}, run_id=result["run_id"])
    result["audit_event_id"] = audit_id
    return result


@app.post("/ai/experiment-summary")
async def experiment_summary(req: ExperimentRequest):
    result = await run_experiment_summary(req)
    audit_id = insert_audit("experiment_summary", "completed", {"request": req.model_dump(), "result": result}, run_id=result["run_id"])
    result["audit_event_id"] = audit_id
    return result


@app.post("/approvals")
def approval_create(req: ApprovalRequest):
    result = create_approval(req.workflow, req.summary, req.payload)
    insert_audit("approval_created", "pending", {**result, "workflow": req.workflow})
    return result


@app.post("/approvals/{approval_id}/decision")
def approval_decision(approval_id: str, req: DecisionRequest):
    try:
        result = decide_approval(approval_id, req.status, req.decided_by, req.decision_note)
    except KeyError as exc:
        raise HTTPException(404, "approval not found") from exc
    insert_audit("approval_decision", req.status, {**result}, actor=req.decided_by)
    return result


@app.post("/webhooks/n8n", dependencies=[Depends(require_hub_api_key)])
async def n8n_webhook(request: Request):
    payload = await request.json()
    event_id = insert_audit("n8n_webhook", "received", payload, actor="n8n")
    return {"received": True, "audit_event_id": event_id}


@app.get("/", response_class=HTMLResponse)
def dashboard():
    html = Path(__file__).with_name("dashboard.html").read_text()
    return HTMLResponse(html)
