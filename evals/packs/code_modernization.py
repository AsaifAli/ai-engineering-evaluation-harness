from __future__ import annotations

from typing import Any

from .base import EvalPack
from ..metrics import exact_match, set_precision_recall_f1


def evaluate(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, float]:
    metrics = {
        "transformation_success": exact_match(actual.get("transformation_success"), expected.get("transformation_success")),
        "syntax_pass_rate": float(bool(actual.get("syntax_valid"))),
        "unit_test_pass_rate": float(actual.get("unit_tests_passed", 0)) / max(1, int(actual.get("unit_tests_total", 1))),
        "semantic_verification": float(bool(actual.get("semantic_verification_passed"))),
        "release_gate": float(bool(actual.get("release_gate_passed"))),
    }
    if expected.get("expected_changed_files") is not None:
        overlap = set_precision_recall_f1(actual.get("changed_files", []), expected.get("expected_changed_files", []))
        metrics["changed_file_f1"] = overlap["f1"]
    return {key: round(float(value), 6) for key, value in metrics.items()}


PACK = EvalPack(
    name="code_modernization",
    evaluator=evaluate,
    gates={"syntax_pass_rate": 1.0, "semantic_verification": 1.0, "release_gate": 1.0, "unit_test_pass_rate": 0.95},
    weights={"transformation_success": 0.15, "syntax_pass_rate": 0.20, "unit_test_pass_rate": 0.25, "semantic_verification": 0.20, "release_gate": 0.20},
    description="Validation of AI-assisted source transformation and release safety.",
    tags=("code", "verification", "release"),
)
