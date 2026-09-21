from __future__ import annotations

from typing import Any

from .base import EvalPack
from ..metrics import set_precision_recall_f1


def evaluate(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, float]:
    test_metrics = set_precision_recall_f1(actual.get("tests", []), expected.get("tests", []))
    defect_metrics = set_precision_recall_f1(actual.get("detected_defects", []), expected.get("defects", []))
    regression_metrics = set_precision_recall_f1(actual.get("regressions", []), expected.get("regressions", []))
    return {
        "test_generation_precision": test_metrics["precision"],
        "test_generation_recall": test_metrics["recall"],
        "test_generation_f1": test_metrics["f1"],
        "defect_detection_precision": defect_metrics["precision"],
        "defect_detection_recall": defect_metrics["recall"],
        "regression_detection_precision": regression_metrics["precision"],
        "regression_detection_recall": regression_metrics["recall"],
        "locator_validity": float(actual.get("locator_validity", 0.0)),
        "execution_success": float(bool(actual.get("execution_success"))),
    }


PACK = EvalPack(
    name="browser_qa",
    evaluator=evaluate,
    gates={"test_generation_f1": 0.85, "defect_detection_recall": 0.85, "regression_detection_precision": 0.85, "locator_validity": 0.95},
    weights={"test_generation_f1": 0.15, "defect_detection_precision": 0.10, "defect_detection_recall": 0.15, "regression_detection_precision": 0.10, "regression_detection_recall": 0.10, "locator_validity": 0.15, "execution_success": 0.15, "test_generation_precision": 0.05, "test_generation_recall": 0.05},
    description="AI-generated browser test and regression quality.",
    tags=("playwright", "regression", "defect-detection"),
)
