from __future__ import annotations

from typing import Any

from .base import EvalPack


def evaluate(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, float]:
    expected_steps = set(map(str, expected.get("required_steps", [])))
    actual_steps = set(map(str, actual.get("completed_steps", [])))
    step_recall = len(expected_steps & actual_steps) / len(expected_steps) if expected_steps else 1.0
    return {
        "task_success": float(actual.get("status") in set(expected.get("success_statuses", ["completed", "completed_with_warnings"]))),
        "step_success": round(step_recall, 6),
        "tool_call_validity": float(actual.get("tool_call_validity", 0.0)),
        "policy_pass_rate": float(actual.get("policy_pass_rate", 0.0)),
        "approval_compliance": float(bool(actual.get("approval_compliant"))),
        "execution_reliability": float(actual.get("execution_reliability", 0.0)),
        "fallback_rate": float(actual.get("fallback_rate", 0.0)),
        "fallback_free_rate": round(1.0 - float(actual.get("fallback_rate", 0.0)), 6),
    }


PACK = EvalPack(
    name="agent_workflow",
    evaluator=evaluate,
    gates={"task_success": 1.0, "step_success": 0.90, "tool_call_validity": 0.95, "policy_pass_rate": 0.95, "approval_compliance": 1.0},
    weights={"task_success": 0.20, "step_success": 0.15, "tool_call_validity": 0.15, "policy_pass_rate": 0.15, "approval_compliance": 0.15, "execution_reliability": 0.10, "fallback_free_rate": 0.10},
    description="Agentic task execution, tool use, policy and approval compliance.",
    tags=("agents", "tools", "policy", "hitl"),
)
