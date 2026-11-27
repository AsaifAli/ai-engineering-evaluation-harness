from __future__ import annotations

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

    return {
        "workflow_completion": round(completion, 6),
        "step_coverage": round(step_coverage, 6),
        "approval_compliance": round(approval_compliance, 6),
        "retry_recovery": round(retry_recovery, 6),
        "state_integrity": round(state_integrity, 6),
        "error_classification_accuracy": round(error_classification_accuracy, 6),
        "audit_traceability": float(actual.get("audit_recorded") is True),
    }


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
    },
    weights={
        "workflow_completion": 0.20,
        "step_coverage": 0.15,
        "approval_compliance": 0.20,
        "retry_recovery": 0.15,
        "state_integrity": 0.15,
        "error_classification_accuracy": 0.05,
        "audit_traceability": 0.10,
    },
    description="Workflow completion, human approval policy, retry recovery and persisted execution-state checks.",
    tags=("workflow", "approvals", "retries", "state", "audit"),
)
