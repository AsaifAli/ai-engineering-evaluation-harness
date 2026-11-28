from __future__ import annotations

import json
from collections import Counter
from typing import Any

from .base import EvalPack


_ALLOWED_TRANSITIONS = {
    "queued": {"running", "cancelled"},
    "running": {"retry_wait", "awaiting_approval", "completed", "completed_with_warnings", "failed", "cancelled"},
    "retry_wait": {"running", "failed", "cancelled"},
    "awaiting_approval": {"completed", "failed", "cancelled"},
}


def _state_sequence_is_valid(transitions: Any) -> bool:
    if not isinstance(transitions, list) or len(transitions) < 2:
        return False
    if any(not isinstance(item, str) for item in transitions):
        return False
    return all(
        transitions[index + 1] in _ALLOWED_TRANSITIONS.get(transitions[index], set())
        for index in range(len(transitions) - 1)
    )


def _tool_name(call: Any) -> str:
    if isinstance(call, str):
        return call
    if isinstance(call, dict):
        return str(call.get("tool") or call.get("name") or call.get("tool_name") or "")
    return ""


def _lcs_length(left: list[str], right: list[str]) -> int:
    previous = [0] * (len(right) + 1)
    for item in left:
        current = [0]
        for index, other in enumerate(right, 1):
            current.append(previous[index - 1] + 1 if item == other else max(previous[index], current[-1]))
        previous = current
    return previous[-1]


def _tool_metrics(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, float]:
    expected_calls = expected.get("expected_tool_calls", [])
    actual_calls = actual.get("tool_calls", [])
    if not isinstance(expected_calls, list) or not isinstance(actual_calls, list):
        raise ValueError("tool call trajectories must be lists")

    expected_names = [_tool_name(call) for call in expected_calls]
    actual_names = [_tool_name(call) for call in actual_calls]
    expected_counts = Counter(name for name in expected_names if name)
    actual_counts = Counter(name for name in actual_names if name)
    overlap = sum((expected_counts & actual_counts).values())
    precision = overlap / sum(actual_counts.values()) if actual_counts else (1.0 if not expected_counts else 0.0)
    recall = overlap / sum(expected_counts.values()) if expected_counts else (1.0 if not actual_counts else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    matched_actual: set[int] = set()
    argument_hits = 0
    for wanted in expected_calls:
        if not isinstance(wanted, dict):
            continue
        for index, observed in enumerate(actual_calls):
            if index in matched_actual or not isinstance(observed, dict):
                continue
            if (
                _tool_name(wanted) == _tool_name(observed)
                and wanted.get("arguments", {}) == observed.get("arguments", {})
            ):
                matched_actual.add(index)
                argument_hits += 1
                break

    denominator = len(expected_calls)
    argument_accuracy = argument_hits / denominator if denominator else (1.0 if not actual_calls else 0.0)
    normalizer = max(len(expected_names), len(actual_names))
    trajectory_similarity = (
        _lcs_length(expected_names, actual_names) / normalizer if normalizer else 1.0
    )
    return {
        "tool_selection_precision": round(precision, 6),
        "tool_selection_recall": round(recall, 6),
        "tool_selection_f1": round(f1, 6),
        "tool_argument_accuracy": round(argument_accuracy, 6),
        "tool_trajectory_similarity": round(trajectory_similarity, 6),
        "tool_trajectory_exact_match": float(expected_names == actual_names),
    }


def evaluate(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, float]:
    required_steps = expected.get("required_steps", [])
    completed_steps = actual.get("completed_steps", [])
    required = set(required_steps) if isinstance(required_steps, list) else set()
    completed = set(completed_steps) if isinstance(completed_steps, list) else set()

    completion = float(actual.get("status") == expected.get("terminal_status"))
    step_coverage = len(required & completed) / len(required) if required else 1.0

    approval_required = expected.get("approval_required") is True
    approval_recorded = actual.get("approval_recorded") is True
    approved = actual.get("approved") is True
    external_action = actual.get("external_action_executed") is True
    approval_compliance = 1.0
    if approval_required and not approval_recorded:
        approval_compliance = 0.0
    if external_action and approval_required and not (approval_recorded and approved):
        approval_compliance = 0.0

    attempts = actual.get("attempts", 1)
    maximum_attempts = expected.get("max_attempts", 1)
    valid_attempt_count = (
        isinstance(attempts, int)
        and not isinstance(attempts, bool)
        and isinstance(maximum_attempts, int)
        and not isinstance(maximum_attempts, bool)
        and 1 <= attempts <= maximum_attempts
    )
    retry_recovery = float(valid_attempt_count)
    if expected.get("retry_expected") is True:
        retry_recovery = float(
            valid_attempt_count
            and attempts >= 2
            and actual.get("status") == expected.get("recovery_terminal_status")
        )

    state_integrity = float(
        actual.get("state_persisted") is True
        and _state_sequence_is_valid(actual.get("state_transitions"))
    )

    expected_failure = expected.get("failure_code")
    error_classification_accuracy = (
        1.0 if expected_failure is None
        else float(actual.get("failure_code") == expected_failure)
    )

    metrics = {
        "workflow_completion": round(completion, 6),
        "step_coverage": round(step_coverage, 6),
        "approval_compliance": round(approval_compliance, 6),
        "retry_recovery": round(retry_recovery, 6),
        "state_integrity": round(state_integrity, 6),
        "error_classification_accuracy": round(error_classification_accuracy, 6),
        "audit_traceability": float(actual.get("audit_recorded") is True),
    }

    if "expected_tool_calls" in expected or "tool_calls" in actual:
        metrics.update(_tool_metrics(expected, actual))

    if "optimal_steps" in expected or "steps_executed" in actual:
        optimal = expected.get("optimal_steps")
        observed = actual.get("steps_executed")
        if (
            isinstance(optimal, int) and not isinstance(optimal, bool) and optimal >= 0
            and isinstance(observed, int) and not isinstance(observed, bool) and observed >= 0
        ):
            metrics["step_efficiency"] = (
                1.0 if optimal == 0 and observed == 0
                else round(min(1.0, optimal / observed), 6) if observed > 0
                else 0.0
            )

    return metrics


PACK = EvalPack(
    name="workflow_orchestration",
    evaluator=evaluate,
    gates={
        "workflow_completion": 1.0,
        "step_coverage": 0.80,
        "approval_compliance": 1.0,
        "retry_recovery": 1.0,
        "state_integrity": 1.0,
        "audit_traceability": 1.0,
        "tool_selection_f1": 0.90,
        "tool_argument_accuracy": 0.90,
        "tool_trajectory_similarity": 0.80,
        "step_efficiency": 0.70,
    },
    weights={
        "workflow_completion": 0.17,
        "step_coverage": 0.12,
        "approval_compliance": 0.17,
        "retry_recovery": 0.12,
        "state_integrity": 0.12,
        "error_classification_accuracy": 0.04,
        "audit_traceability": 0.08,
        "tool_selection_f1": 0.06,
        "tool_argument_accuracy": 0.05,
        "tool_trajectory_similarity": 0.05,
        "step_efficiency": 0.02,
    },
    description="Workflow completion, approvals, recovery, execution state, agent tool selection, argument correctness and trajectory efficiency.",
    tags=("workflow", "agent-trajectory", "tool-use", "approvals", "retries", "state", "audit"),
)
