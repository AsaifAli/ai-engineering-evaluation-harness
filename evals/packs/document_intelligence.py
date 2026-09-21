from __future__ import annotations

from typing import Any

from .base import EvalPack
from ..metrics import exact_match, mean


def evaluate(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, float]:
    expected_fields = expected.get("fields", {})
    actual_fields = actual.get("fields", {})
    keys = sorted(set(expected_fields) | set(actual_fields))
    exact = [exact_match(actual_fields.get(key), expected_fields.get(key)) for key in keys]
    critical = expected.get("critical_fields", keys)
    critical_exact = [exact_match(actual_fields.get(key), expected_fields.get(key)) for key in critical]
    risk_correct = exact_match(actual.get("risk_label"), expected.get("risk_label"))
    return {
        "field_exact_match": round(mean(exact), 6),
        "critical_field_accuracy": round(mean(critical_exact), 6),
        "schema_validity": float(bool(actual.get("schema_valid"))),
        "numeric_accuracy": float(actual.get("numeric_accuracy", 0.0)),
        "risk_accuracy": risk_correct,
        "risk_f1": risk_correct,
        "recommendation_consistency": float(actual.get("recommendation_consistency", 0.0)),
    }


PACK = EvalPack(
    name="document_intelligence",
    evaluator=evaluate,
    gates={"field_exact_match": 0.90, "critical_field_accuracy": 0.95, "schema_validity": 1.0, "risk_f1": 0.85},
    weights={"field_exact_match": 0.20, "critical_field_accuracy": 0.20, "schema_validity": 0.15, "numeric_accuracy": 0.10, "risk_f1": 0.15, "recommendation_consistency": 0.20},
    description="Structured document extraction, validation and decision-quality checks.",
    tags=("extraction", "schema", "risk"),
)
