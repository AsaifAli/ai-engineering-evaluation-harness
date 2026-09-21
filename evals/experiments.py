from __future__ import annotations

from typing import Any

from app.db import get_quality_batch

LOWER_IS_BETTER_DEFAULT = {
    "latency", "latency_ms", "response_time", "response_time_ms", "inference_time", "inference_time_ms",
    "duration", "duration_ms", "loss", "error", "error_rate", "cost", "cost_usd", "memory_mb", "memory_gb",
    "fallback_rate",
}


def _metric_direction(metric: str) -> str:
    return "lower" if metric.lower() in LOWER_IS_BETTER_DEFAULT else "higher"


def compare_batches(*, target: str, baseline_batch_id: str, candidate_batch_id: str) -> dict[str, Any]:
    baseline = get_quality_batch(target, baseline_batch_id)
    candidate = get_quality_batch(target, candidate_batch_id)
    if not baseline:
        raise KeyError(f"baseline batch not found for {target}: {baseline_batch_id}")
    if not candidate:
        raise KeyError(f"candidate batch not found for {target}: {candidate_batch_id}")

    baseline_by_case = {row["case_id"]: row for row in baseline}
    candidate_by_case = {row["case_id"]: row for row in candidate}
    common_cases = sorted(set(baseline_by_case) & set(candidate_by_case))

    metric_names = sorted({m for row in baseline for m in row["metrics"]} | {m for row in candidate for m in row["metrics"]})
    metrics: dict[str, Any] = {}
    regressions: list[str] = []
    improvements: list[str] = []
    for metric in metric_names:
        bvals = [float(baseline_by_case[c]["metrics"][metric]) for c in common_cases if metric in baseline_by_case[c]["metrics"]]
        cvals = [float(candidate_by_case[c]["metrics"][metric]) for c in common_cases if metric in candidate_by_case[c]["metrics"]]
        if not bvals or not cvals:
            continue
        b = sum(bvals) / len(bvals)
        c = sum(cvals) / len(cvals)
        delta = round(c - b, 6)
        direction = _metric_direction(metric)
        is_regression = delta < -0.000001 if direction == "higher" else delta > 0.000001
        is_improvement = delta > 0.000001 if direction == "higher" else delta < -0.000001
        metrics[metric] = {
            "baseline": round(b, 6),
            "candidate": round(c, 6),
            "delta": delta,
            "direction": direction,
            "regression": is_regression,
            "improvement": is_improvement,
        }
        if is_regression:
            regressions.append(metric)
        if is_improvement:
            improvements.append(metric)

    baseline_score = sum(float(row["score"]) for row in baseline) / len(baseline)
    candidate_score = sum(float(row["score"]) for row in candidate) / len(candidate)
    return {
        "target": target,
        "baseline_batch_id": baseline_batch_id,
        "candidate_batch_id": candidate_batch_id,
        "common_cases": common_cases,
        "baseline_score": round(baseline_score, 6),
        "candidate_score": round(candidate_score, 6),
        "score_delta": round(candidate_score - baseline_score, 6),
        "metrics": metrics,
        "regressions": sorted(regressions),
        "improvements": sorted(improvements),
        "status": "regression" if regressions else "improved" if improvements else "unchanged",
        "passed": not regressions and all(row["passed"] for row in candidate),
    }
