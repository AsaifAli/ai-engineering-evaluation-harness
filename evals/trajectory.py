from __future__ import annotations

import math
from typing import Any

from app.harness import AgentRun


def _quality_score(gate: dict[str, Any]) -> float | None:
    value = gate.get("quality_score")
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
        and 0 <= value <= 100
    ):
        return float(value)
    return None


def _required_check_summary(
    gate: dict[str, Any],
) -> tuple[float | None, dict[str, int]]:
    checks = gate.get("checks")
    if not isinstance(checks, list):
        return None, {}

    required = [
        item for item in checks
        if isinstance(item, dict) and item.get("required") is True
    ]
    if not required:
        return None, {}

    statuses = [str(item.get("status") or "").lower() for item in required]
    allowed = {"passed", "failed", "unavailable", "skipped"}

    if any(status not in allowed for status in statuses):
        return None, {}

    counts = {
        status: statuses.count(status)
        for status in sorted(allowed)
    }
    return round(counts["passed"] / len(required), 6), {
        "required": len(required),
        "passed": counts["passed"],
        "failed": counts["failed"],
        "unavailable": counts["unavailable"],
        "skipped": counts["skipped"],
    }


def _semantic_result(
    output: dict[str, Any],
    gate: dict[str, Any],
) -> tuple[float | None, str | None]:
    semantic_gate = gate.get("semantic_gate")

    if isinstance(semantic_gate, dict):
        gate_status = str(semantic_gate.get("status") or "").lower()
        semantic_status = str(
            semantic_gate.get("semantic_status") or ""
        ).lower()

        if gate_status == "passed" or semantic_status == "verified":
            return 1.0, "quality_gate.semantic_gate"

        if gate_status in {"blocked", "failed"} or semantic_status in {
            "blocked", "failed"
        }:
            return 0.0, "quality_gate.semantic_gate"

    verification = output.get("semantic_verification")
    if isinstance(verification, dict):
        status = str(verification.get("status") or "").lower()
        if status == "verified":
            return 1.0, "output.semantic_verification.status"
        if status in {"blocked", "failed"}:
            return 0.0, "output.semantic_verification.status"

    return None, None


def _release_result(
    output: dict[str, Any],
    gate: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[float | None, str | None]:
    for source_name, source in (
        ("quality_gate", gate),
        ("output", output),
        ("metadata", metadata),
    ):
        value = source.get("release_ready")
        if isinstance(value, bool):
            return float(value), f"{source_name}.release_ready"

    return None, None


def evaluate_live_trajectory(
    target: str,
    run: AgentRun,
) -> dict[str, Any] | None:
    """Evaluate LegacyLens using its actual live quality-gate response."""
    if target != "legacylens":
        return None

    output = run.output if isinstance(run.output, dict) else {}
    metadata = run.metadata if isinstance(run.metadata, dict) else {}

    gate = output.get("quality_gate")
    if not isinstance(gate, dict):
        gate = metadata.get("quality_gate")
    if not isinstance(gate, dict):
        gate = {}

    metrics: dict[str, float] = {}
    sources: dict[str, str] = {}
    unavailable: dict[str, str] = {}

    quality_score = _quality_score(gate)
    if quality_score is not None:
        metrics["quality_score"] = round(quality_score / 100.0, 6)
        sources["quality_score"] = "quality_gate.quality_score"
    else:
        unavailable["quality_score"] = (
            "The live target did not expose a numeric quality_score from 0 to 100."
        )

    check_rate, check_counts = _required_check_summary(gate)
    if check_rate is not None:
        metrics["required_check_pass_rate"] = check_rate
        sources["required_check_pass_rate"] = (
            "quality_gate.checks: required checks"
        )
    else:
        unavailable["required_check_pass_rate"] = (
            "No complete list of required validation checks was exposed."
        )

    semantic_value, semantic_source = _semantic_result(output, gate)
    if semantic_value is not None:
        metrics["semantic_verification"] = semantic_value
        sources["semantic_verification"] = semantic_source or "live response"
    else:
        unavailable["semantic_verification"] = (
            "No explicit semantic verification outcome was exposed."
        )

    release_value, release_source = _release_result(
        output, gate, metadata
    )
    if release_value is not None:
        metrics["release_gate"] = release_value
        sources["release_gate"] = release_source or "live response"
    else:
        unavailable["release_gate"] = (
            "No explicit release_ready decision was exposed."
        )

    required_metrics = (
        "quality_score",
        "required_check_pass_rate",
        "semantic_verification",
        "release_gate",
    )
    missing = [name for name in required_metrics if name not in metrics]
    complete = not missing

    failures: list[str] = []
    if complete:
        if metrics["required_check_pass_rate"] < 1.0:
            failures.append("required_check_pass_rate<1.0")
        if metrics["semantic_verification"] < 1.0:
            failures.append("semantic_verification<1.0")
        if metrics["release_gate"] < 1.0:
            failures.append("release_gate<1.0")

    trace = run.trace if isinstance(run.trace, list) else []
    progress_events = sum(
        isinstance(item, dict)
        and item.get("event_type") == "workflow_progress"
        for item in trace
    )
    plan_steps = sum(
        isinstance(item, dict)
        and item.get("event_type") == "workflow_step"
        for item in trace
    )
    terminal_events = [
        item for item in trace
        if isinstance(item, dict)
        and item.get("event_type") == "task_outcome"
    ]

    repair_history = gate.get("repair_history")
    repair_cycles = (
        len(repair_history) if isinstance(repair_history, list) else None
    )

    return {
        "evaluation_type": "live_trajectory",
        "evaluation_pack": "legacylens_live_quality_gate",
        "evaluation_status": "complete" if complete else "incomplete",
        "score": metrics.get("quality_score") if complete else None,
        "score_percent": quality_score if complete else None,
        "score_source": "LegacyLens quality_gate.quality_score" if complete else None,
        "passed": (not failures) if complete else None,
        "metrics": metrics,
        "metric_sources": sources,
        "unavailable_metrics": unavailable,
        "missing_required_metrics": missing,
        "gate_failures": failures,
        "run_outcome": {
            "task_status": run.status,
            "target_status": output.get("status"),
            "release_ready": (
                bool(release_value) if release_value is not None else None
            ),
        },
        "native_evidence": {
            "required_check_counts": check_counts,
            "repair_cycles": repair_cycles,
            "progress_events": progress_events,
            "final_plan_steps": plan_steps,
            "terminal_events": len(terminal_events),
            "duration_ms": run.duration_ms,
        },
        "notes": [
            "The score is LegacyLens's own deterministic quality score, "
            "normalized to the range 0 to 1.",
            "Release readiness also depends on semantic verification; "
            "it is reported separately from the deterministic quality score.",
            "Missing evidence is reported as unavailable, never as a zero score.",
        ],
    }