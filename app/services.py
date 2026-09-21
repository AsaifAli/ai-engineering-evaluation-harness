from __future__ import annotations

import json
import time
import uuid
from typing import Any, Dict

from . import gateway
from .config import LLM_PROVIDER
from .db import insert_llm_run
from .guardrails import policy_for_action, sanitize_untrusted_text, guardrail_status
from .models import ExperimentDecision, ExperimentRequest, IssueDecision, IssueRequest, PRDecision, PRRequest
from .prompts import EXPERIMENT_SUMMARY_VERSION, EXPERIMENT_SYSTEM, ISSUE_SYSTEM, ISSUE_TRIAGE_VERSION, PR_REVIEW_VERSION, PR_SYSTEM


LOWER_IS_BETTER = {
    "latency", "latency_ms", "response_time", "response_time_ms", "inference_time", "inference_time_ms",
    "duration", "duration_ms", "loss", "error", "error_rate", "cost", "cost_usd", "memory_mb", "memory_gb",
}


def _record_run(*, run_id: str, workflow: str, operation: str, provider: str, model: str,
                prompt_version: str, latency_ms: float, status: str, fallback_used: bool,
                input_tokens: Any = None, output_tokens: Any = None, total_tokens: Any = None,
                estimated_cost_usd: Any = None, guardrail: str = "passed", error: str | None = None) -> None:
    insert_llm_run(run_id=run_id, workflow=workflow, operation=operation, provider=provider, model=model,
                   prompt_version=prompt_version, latency_ms=latency_ms, status=status,
                   fallback_used=fallback_used, input_tokens=input_tokens, output_tokens=output_tokens,
                   total_tokens=total_tokens, estimated_cost_usd=estimated_cost_usd,
                   guardrail_status=guardrail, error=error)


def heuristic_triage(req: IssueRequest) -> Dict[str, Any]:
    text = f"{req.title} {req.body}".lower()
    security_terms = ["security", "credential", "secret", "token leaked", "vulnerability", "cve", "exploit"]
    bug_terms = ["bug", "error", "exception", "crash", "failed", "failure", "broken", "regression"]
    ml_terms = ["model", "training", "inference", "embedding", "rag", "llm", "agent", "vector"]
    security = any(x in text for x in security_terms)
    bug = any(x in text for x in bug_terms)
    ml = any(x in text for x in ml_terms)
    priority = "critical" if security and any(x in text for x in ["leaked", "exploit", "production"]) else "high" if security else "medium" if ml else "high" if bug else "low"
    category = "security" if security else "ai-ml" if ml else "bug" if bug else "engineering"
    labels = [f"ai:{category}", f"priority:{priority}"]
    return {
        "category": category,
        "priority": priority,
        "labels": labels,
        "summary": req.title[:160],
        "recommended_action": (
            "Escalate for immediate security review and rotate affected credentials if exposure is confirmed." if security else
            "Assign an engineering owner, reproduce the issue, and review within the normal SLA." if bug else
            "Route to the AI/ML owner and review model, data, or retrieval context before changing production behavior." if ml else
            "Assign an engineering owner and triage against the normal backlog SLA."
        ),
        "confidence": 0.88 if security or bug else 0.76,
        "requires_human_approval": True,
    }


def heuristic_pr(req: PRRequest) -> Dict[str, Any]:
    text = f"{req.title} {req.body} {req.diff or ''}".lower()
    security = any(x in text for x in ["auth", "secret", "credential", "permission", "token"])
    infra = any(x in text for x in ["docker", "terraform", "deploy", "migration", "database"])
    size_score = req.changed_files * 1.5 + req.additions / 100 + req.deletions / 150
    risk = "high" if security or size_score >= 45 else "medium" if infra or size_score >= 18 else "low"
    checks = ["tests and regression coverage", "error handling and observability", "configuration/secrets hygiene"]
    if security:
        checks.insert(0, "authentication/authorization and secret exposure")
    if infra:
        checks.append("deployment, migration and rollback safety")
    return {
        "risk": risk,
        "risk_score": round(min(100, size_score + (30 if security else 0) + (15 if infra else 0)), 1),
        "review_summary": req.title[:180],
        "recommended_checks": checks,
        "requires_human_approval": True,
    }


def experiment_findings(req: ExperimentRequest) -> Dict[str, Any]:
    deltas = {}
    for key, value in req.metrics.items():
        base = req.baseline.get(key)
        if isinstance(value, (int, float)) and isinstance(base, (int, float)) and base != 0:
            deltas[key] = round((value - base) / abs(base) * 100, 2)
    regressions: list[str] = []
    improvements: list[str] = []
    for key, delta in deltas.items():
        lower = key.lower() in LOWER_IS_BETTER
        if lower:
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
    }


async def run_issue_triage(req: IssueRequest) -> Dict[str, Any]:
    run_id = str(uuid.uuid4())
    guard = sanitize_untrusted_text(f"TITLE: {req.title}\nBODY: {req.body}")
    start = time.perf_counter()
    try:
        if LLM_PROVIDER == "gateway" and gateway.configured():
            response = await gateway.chat_json(
                system_prompt=ISSUE_SYSTEM,
                user_prompt=json.dumps({"title": guard.text[:2000], "body": guard.text, "labels": req.labels, "repository": req.repository, "author": req.author}),
                workflow="issue_triage", prompt_version=ISSUE_TRIAGE_VERSION,
            )
            decision = IssueDecision.model_validate(response.data)
            policy = policy_for_action(injection_detected=guard.injection_detected, confidence=decision.confidence)
            _record_run(run_id=run_id, workflow="issue_triage", operation="classify", provider=response.provider, model=response.model,
                        prompt_version=ISSUE_TRIAGE_VERSION, latency_ms=response.latency_ms, status="success", fallback_used=False,
                        input_tokens=response.prompt_tokens, output_tokens=response.output_tokens, total_tokens=response.total_tokens,
                        estimated_cost_usd=response.estimated_cost_usd, guardrail=guardrail_status(guard))
            return {
                **decision.model_dump(), "run_id": run_id, "model": response.model, "provider": response.provider,
                "prompt_version": ISSUE_TRIAGE_VERSION, "guardrail_status": guardrail_status(guard),
                "guardrail_reasons": guard.reasons, "redactions": guard.redactions, "policy": policy, "ai_source": "gateway",
            }
    except Exception as exc:
        _record_run(run_id=run_id, workflow="issue_triage", operation="classify", provider="gateway", model="unknown",
                    prompt_version=ISSUE_TRIAGE_VERSION, latency_ms=round((time.perf_counter()-start)*1000,2),
                    status="failed", fallback_used=True, guardrail=guardrail_status(guard), error=str(exc))
        fallback_reason = str(exc)
    else:
        fallback_reason = None
    start = time.perf_counter()
    data = heuristic_triage(req)
    policy = policy_for_action(injection_detected=guard.injection_detected, confidence=data["confidence"])
    _record_run(run_id=run_id, workflow="issue_triage", operation="classify", provider="deterministic",
                model="deterministic-fallback-v2", prompt_version=ISSUE_TRIAGE_VERSION,
                latency_ms=round((time.perf_counter()-start)*1000,2), status="success", fallback_used=True,
                guardrail=guardrail_status(guard), error=fallback_reason if 'fallback_reason' in locals() else None)
    return {
        **data, "run_id": run_id, "model": "deterministic-fallback-v2", "provider": "deterministic",
        "prompt_version": ISSUE_TRIAGE_VERSION, "guardrail_status": guardrail_status(guard),
        "guardrail_reasons": guard.reasons, "redactions": guard.redactions, "policy": policy,
        "ai_source": "deterministic_fallback", **({"fallback_reason": fallback_reason} if fallback_reason else {}),
    }


async def run_pr_review(req: PRRequest) -> Dict[str, Any]:
    run_id = str(uuid.uuid4())
    guard = sanitize_untrusted_text(f"TITLE: {req.title}\nBODY: {req.body}\nDIFF: {req.diff or ''}")
    start = time.perf_counter()
    try:
        if LLM_PROVIDER == "gateway" and gateway.configured():
            response = await gateway.chat_json(
                system_prompt=PR_SYSTEM,
                user_prompt=json.dumps({"title": req.title, "body": guard.text[:4000], "changed_files": req.changed_files, "additions": req.additions, "deletions": req.deletions, "repository": req.repository, "author": req.author, "diff": guard.text[-6000:]}),
                workflow="pr_review", prompt_version=PR_REVIEW_VERSION,
            )
            decision = PRDecision.model_validate(response.data)
            policy = {"action_allowed": False if guard.injection_detected else True, "requires_human_approval": True,
                      "action_scope": "manual_review_only" if guard.injection_detected else "bounded_engineering_action",
                      "policy_reasons": ["prompt-injection-signal"] if guard.injection_detected else []}
            _record_run(run_id=run_id, workflow="pr_review", operation="risk_review", provider=response.provider, model=response.model,
                        prompt_version=PR_REVIEW_VERSION, latency_ms=response.latency_ms, status="success", fallback_used=False,
                        input_tokens=response.prompt_tokens, output_tokens=response.output_tokens, total_tokens=response.total_tokens,
                        estimated_cost_usd=response.estimated_cost_usd, guardrail=guardrail_status(guard))
            return {**decision.model_dump(), "run_id": run_id, "model": response.model, "provider": response.provider,
                    "prompt_version": PR_REVIEW_VERSION, "guardrail_status": guardrail_status(guard), "guardrail_reasons": guard.reasons,
                    "redactions": guard.redactions, "policy": policy, "ai_source": "gateway"}
    except Exception as exc:
        _record_run(run_id=run_id, workflow="pr_review", operation="risk_review", provider="gateway", model="unknown",
                    prompt_version=PR_REVIEW_VERSION, latency_ms=round((time.perf_counter()-start)*1000,2),
                    status="failed", fallback_used=True, guardrail=guardrail_status(guard), error=str(exc))
        fallback_reason = str(exc)
    else:
        fallback_reason = None
    start = time.perf_counter()
    data = heuristic_pr(req)
    _record_run(run_id=run_id, workflow="pr_review", operation="risk_review", provider="deterministic", model="deterministic-fallback-v2",
                prompt_version=PR_REVIEW_VERSION, latency_ms=round((time.perf_counter()-start)*1000,2), status="success",
                fallback_used=True, guardrail=guardrail_status(guard), error=fallback_reason if 'fallback_reason' in locals() else None)
    return {**data, "run_id": run_id, "model": "deterministic-fallback-v2", "provider": "deterministic",
            "prompt_version": PR_REVIEW_VERSION, "guardrail_status": guardrail_status(guard), "guardrail_reasons": guard.reasons,
            "redactions": guard.redactions, "policy": {"action_allowed": False if guard.injection_detected else True,
            "requires_human_approval": True, "action_scope": "manual_review_only" if guard.injection_detected else "bounded_engineering_action",
            "policy_reasons": ["prompt-injection-signal"] if guard.injection_detected else []},
            "ai_source": "deterministic_fallback", **({"fallback_reason": fallback_reason} if fallback_reason else {})}


async def run_experiment_summary(req: ExperimentRequest) -> Dict[str, Any]:
    run_id = str(uuid.uuid4())
    findings = experiment_findings(req)
    start = time.perf_counter()
    base_summary = (
        f"Compared {len(findings['relative_deltas_pct'])} metrics against baseline; "
        f"{len(findings['regressions'])} potential regressions and {len(findings['improvements'])} meaningful improvements detected."
    )
    base_action = "Review regressions before distribution." if findings["regressions"] else "Review the experiment summary before distribution."
    if LLM_PROVIDER == "gateway" and gateway.configured():
        try:
            response = await gateway.chat_json(
                system_prompt=EXPERIMENT_SYSTEM,
                user_prompt=json.dumps({**findings, "metadata": req.metadata}),
                workflow="experiment_summary", prompt_version=EXPERIMENT_SUMMARY_VERSION,
            )
            decision = ExperimentDecision.model_validate(response.data)
            _record_run(run_id=run_id, workflow="experiment_summary", operation="summarize", provider=response.provider, model=response.model,
                        prompt_version=EXPERIMENT_SUMMARY_VERSION, latency_ms=response.latency_ms, status="success", fallback_used=False,
                        input_tokens=response.prompt_tokens, output_tokens=response.output_tokens, total_tokens=response.total_tokens,
                        estimated_cost_usd=response.estimated_cost_usd, guardrail="passed")
            return {**findings, **decision.model_dump(), "run_id": run_id, "model": response.model, "provider": response.provider,
                    "prompt_version": EXPERIMENT_SUMMARY_VERSION, "guardrail_status": "passed", "ai_source": "gateway",
                    "requires_human_approval": True}
        except Exception as exc:
            _record_run(run_id=run_id, workflow="experiment_summary", operation="summarize", provider="gateway", model="unknown",
                        prompt_version=EXPERIMENT_SUMMARY_VERSION, latency_ms=round((time.perf_counter()-start)*1000,2), status="failed",
                        fallback_used=True, guardrail="passed", error=str(exc))
            fallback_reason = str(exc)
    else:
        fallback_reason = None
    _record_run(run_id=run_id, workflow="experiment_summary", operation="summarize", provider="deterministic", model="deterministic-fallback-v2",
                prompt_version=EXPERIMENT_SUMMARY_VERSION, latency_ms=round((time.perf_counter()-start)*1000,2), status="success",
                fallback_used=True, guardrail="passed", error=fallback_reason if 'fallback_reason' in locals() else None)
    return {**findings, "summary": base_summary, "next_action": base_action, "run_id": run_id,
            "model": "deterministic-fallback-v2", "provider": "deterministic", "prompt_version": EXPERIMENT_SUMMARY_VERSION,
            "guardrail_status": "passed", "ai_source": "deterministic_fallback", "requires_human_approval": True,
            **({"fallback_reason": fallback_reason} if fallback_reason else {})}
