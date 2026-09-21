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


def evaluate_case(target: str, case_id: str, expected: dict[str, Any], actual: dict[str, Any], *, mode: str) -> ProjectEval:
    """Evaluate a case through the target's reusable evaluation pack."""
    from app.targets import TARGETS

    spec = next((item for item in TARGETS if item.slug == target), None)
    if spec is None:
        raise KeyError(f"unknown target: {target}")

    pack = get_pack(spec.evaluation_pack)
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


# Compatibility exports for callers that historically imported these symbols.
EVALUATORS = {}
for _target in ("evidenceflow", "legacylens", "quotesense", "webqa", "flowpilot"):
    from app.targets import TARGETS
    _spec = next(item for item in TARGETS if item.slug == _target)
    EVALUATORS[_target] = get_pack(_spec.evaluation_pack).evaluator

DEFAULT_GATES = {}
WEIGHTS = {}
for _target in EVALUATORS:
    from app.targets import TARGETS
    _spec = next(item for item in TARGETS if item.slug == _target)
    _pack = get_pack(_spec.evaluation_pack)
    DEFAULT_GATES[_target] = _pack.gates
    WEIGHTS[_target] = _pack.weights

__all__ = ["ProjectEval", "MetricFn", "evaluate_case", "EVALUATORS", "DEFAULT_GATES", "WEIGHTS", "pack_catalog"]
