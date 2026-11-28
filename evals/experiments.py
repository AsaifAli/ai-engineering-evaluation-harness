from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable


_ALLOWED_GROUP_FIELDS = {
    "experiment_id",
    "model_version",
    "prompt_version",
    "config_version",
    "dataset_version",
    "target",
}


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def compare_experiments(
    runs: Iterable[dict[str, Any]],
    *,
    target: str | None = None,
    baseline_experiment_id: str | None = None,
    group_by: tuple[str, ...] = ("experiment_id",),
    regression_threshold: float = 0.02,
) -> dict[str, Any]:
    """Aggregate stored replay/live evaluation rows and compare them with a baseline.

    Only version identifiers and aggregate scores/metrics are used. Raw prompts,
    outputs, documents, traces and other content are intentionally not accepted
    as grouping dimensions or included in the result.
    """
    if not group_by or any(field not in _ALLOWED_GROUP_FIELDS for field in group_by):
        raise ValueError(f"group_by fields must be selected from {sorted(_ALLOWED_GROUP_FIELDS)}")
    if not _finite_number(regression_threshold) or regression_threshold < 0:
        raise ValueError("regression_threshold must be a finite non-negative number")

    selected = [
        row for row in runs
        if isinstance(row, dict) and (target is None or row.get("target") == target)
    ]
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    group_ids: dict[tuple[str, ...], str] = {}

    for row in selected:
        values = tuple(str(row.get(field) or "") for field in group_by)
        # Rows created before experiment IDs were introduced remain comparable
        # via model/prompt/config/dataset lineage.
        if all(not value for value in values):
            fallback = ("model_version", "prompt_version", "config_version", "dataset_version")
            values = tuple(str(row.get(field) or "not-applicable") for field in fallback)
            identifier = "legacy:" + "|".join(f"{field}={value}" for field, value in zip(fallback, values))
        else:
            identifier = "|".join(f"{field}={value or 'unspecified'}" for field, value in zip(group_by, values))
        groups[values].append(row)
        group_ids[values] = str(row.get("experiment_id") or identifier)

    summaries: list[dict[str, Any]] = []
    for key, items in groups.items():
        scores = [float(item["score"]) for item in items if _finite_number(item.get("score"))]
        metric_values: dict[str, list[float]] = defaultdict(list)
        for item in items:
            metrics = item.get("metrics", {})
            if not isinstance(metrics, dict):
                continue
            for name, value in metrics.items():
                if _finite_number(value):
                    metric_values[str(name)].append(float(value))
        metric_means = {
            name: round(sum(values) / len(values), 6)
            for name, values in sorted(metric_values.items())
            if values
        }
        dates = [str(item.get("created_at")) for item in items if item.get("created_at")]
        pass_values = [bool(item.get("passed")) for item in items if "passed" in item]
        lineage = {
            field: items[0].get(field)
            for field in ("model_version", "prompt_version", "config_version", "dataset_version", "target")
            if items[0].get(field) is not None
        }
        explicit_id = items[0].get("experiment_id")
        summaries.append({
            "experiment_id": str(explicit_id) if explicit_id else group_ids[key],
            "lineage": lineage,
            "runs": len(items),
            "score": round(sum(scores) / len(scores), 6) if scores else None,
            "pass_rate": round(sum(pass_values) / len(pass_values), 6) if pass_values else None,
            "metrics": metric_means,
            "first_seen": min(dates) if dates else None,
            "last_seen": max(dates) if dates else None,
        })

    if baseline_experiment_id is not None:
        baseline = next(
            (item for item in summaries if item["experiment_id"] == baseline_experiment_id),
            None,
        )
        if baseline is None:
            raise ValueError("baseline_experiment_id was not found in the selected runs")
    else:
        baseline = min(
            summaries,
            key=lambda item: item["first_seen"] or "",
            default=None,
        )

    baseline_score = baseline.get("score") if baseline else None
    baseline_metrics = baseline.get("metrics", {}) if baseline else {}
    compared: list[dict[str, Any]] = []
    for item in summaries:
        score_delta = (
            round(item["score"] - baseline_score, 6)
            if item["score"] is not None and baseline_score is not None
            else None
        )
        metric_deltas = {
            name: round(value - baseline_metrics[name], 6)
            for name, value in item["metrics"].items()
            if name in baseline_metrics
        }
        regressions = sorted(
            name for name, delta in metric_deltas.items()
            if delta < -regression_threshold
        )
        compared.append({
            **item,
            "is_baseline": bool(baseline and item["experiment_id"] == baseline["experiment_id"]),
            "score_delta": score_delta,
            "metric_deltas": metric_deltas,
            "regressions": regressions,
            "regression_detected": bool(regressions) or (
                score_delta is not None and score_delta < -regression_threshold
            ),
        })

    return {
        "target": target,
        "baseline_experiment_id": baseline["experiment_id"] if baseline else None,
        "regression_threshold": regression_threshold,
        "experiment_count": len(compared),
        "experiments": compared,
    }
