from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .registry import get_pack, pack_catalog


@dataclass(frozen=True)
class ProjectEval:
    target: str
    case_id: str
    mode: str
    metrics: dict[str, float]
    score: float
    passed: bool
    gate_failures: list[str]
    notes: list[str]


MetricFn = Callable[[dict[str, Any], dict[str, Any]], dict[str, float]]

PROJECT_PACKS = {
    "evidenceflow": "rag",
    "quotesense": "document_intelligence",
}


def evaluate_case(
    target: str,
    case_id: str,
    expected: dict[str, Any],
    actual: dict[str, Any],
    *,
    mode: str,
) -> ProjectEval:
    """Evaluate one EvidenceFlow or QuoteSense fixture against its quality pack."""
    pack_name = PROJECT_PACKS.get(target)
    if pack_name is None:
        raise KeyError(f"unknown evaluation target: {target}")
    pack = get_pack(pack_name)
    metrics = pack.evaluator(expected, actual)
    weighted = 0.0
    total_weight = 0.0
    for metric, weight in pack.weights.items():
        if metric in metrics:
            weighted += float(metrics[metric]) * weight
            total_weight += weight
    score = round(weighted / total_weight, 6) if total_weight else 0.0
    failures = [
        f"{metric}<{threshold}"
        for metric, threshold in pack.gates.items()
        if metric in metrics and metrics[metric] < threshold
    ]
    notes = [
        "Replay fixtures are reference measurements, not production LLM quality claims."
    ] if mode == "replay" else []
    return ProjectEval(target, case_id, mode, metrics, score, not failures, failures, notes)


EVALUATORS = {
    target: get_pack(pack_name).evaluator
    for target, pack_name in PROJECT_PACKS.items()
}
DEFAULT_GATES = {
    target: get_pack(pack_name).gates
    for target, pack_name in PROJECT_PACKS.items()
}
WEIGHTS = {
    target: get_pack(pack_name).weights
    for target, pack_name in PROJECT_PACKS.items()
}

__all__ = [
    "ProjectEval",
    "MetricFn",
    "evaluate_case",
    "EVALUATORS",
    "DEFAULT_GATES",
    "WEIGHTS",
    "pack_catalog",
]
