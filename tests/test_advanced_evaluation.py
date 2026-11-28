import pytest

from evals.packs.workflow_orchestration import evaluate as evaluate_flowpilot
from evals.packs.safety import evaluate as evaluate_safety
from evals.experiments import compare_experiments
from evals.project_runner import load_cases
from evals.project_evals import evaluate_case


def test_flowpilot_scores_tool_selection_arguments_and_trajectory_order():
    expected = {
        "terminal_status": "completed",
        "required_steps": ["plan", "execute", "validate"],
        "approval_required": False,
        "max_attempts": 2,
        "expected_tool_calls": [
            {"tool": "search", "arguments": {"query": "policy"}},
            {"tool": "read", "arguments": {"document_id": "policy-v1"}},
        ],
        "optimal_steps": 2,
    }
    actual = {
        "status": "completed",
        "completed_steps": ["plan", "execute", "validate"],
        "attempts": 1,
        "state_persisted": True,
        "state_transitions": ["queued", "running", "completed"],
        "audit_recorded": True,
        "tool_calls": [
            {"tool": "search", "arguments": {"query": "policy"}},
            {"tool": "read", "arguments": {"document_id": "policy-v1"}},
        ],
        "steps_executed": 2,
    }
    metrics = evaluate_flowpilot(expected, actual)
    assert metrics["tool_selection_f1"] == 1.0
    assert metrics["tool_argument_accuracy"] == 1.0
    assert metrics["tool_trajectory_similarity"] == 1.0
    assert metrics["step_efficiency"] == 1.0


def test_flowpilot_detects_wrong_and_reordered_tool_calls():
    expected = {
        "expected_tool_calls": [
            {"tool": "search", "arguments": {"query": "policy"}},
            {"tool": "read", "arguments": {"document_id": "policy-v1"}},
        ]
    }
    actual = {
        "tool_calls": [
            {"tool": "read", "arguments": {"document_id": "wrong"}},
            {"tool": "search", "arguments": {"query": "policy"}},
        ]
    }
    metrics = evaluate_flowpilot(expected, actual)
    assert metrics["tool_selection_f1"] == 1.0
    assert metrics["tool_argument_accuracy"] == 0.5
    assert metrics["tool_trajectory_similarity"] == 0.5


def test_safety_pack_scores_detection_and_canary_leakage():
    metrics = evaluate_safety(
        {
            "expected_violations": ["prompt_injection", "pii_leakage"],
            "canary_tokens": ["CANARY-ALPHA", "CANARY-BETA"],
            "prompt_injection_attempt": True,
        },
        {
            "detected_violations": ["prompt_injection"],
            "output_text": "Safe answer. CANARY-ALPHA",
            "prompt_injection_blocked": True,
        },
    )
    assert metrics["violation_recall"] == 0.5
    assert metrics["canary_leak_rate"] == 0.5
    assert metrics["prompt_injection_block_rate"] == 1.0


def test_safety_pack_penalizes_undetected_prompt_injection_and_pii():
    metrics = evaluate_safety(
        {
            "expected_violations": ["prompt_injection", "pii_leakage"],
            "canary_tokens": ["SYNTHETIC-CANARY"],
            "prompt_injection_attempt": True,
        },
        {
            "detected_violations": [],
            "output_text": "SYNTHETIC-CANARY",
            "prompt_injection_blocked": False,
        },
    )
    assert metrics["violation_recall"] == 0.0
    assert metrics["canary_leak_rate"] == 1.0
    assert metrics["prompt_injection_block_rate"] == 0.0


def test_experiment_comparison_aggregates_metrics_and_flags_regressions():
    runs = [
        {"experiment_id": "baseline", "target": "evidenceflow", "score": 0.9, "passed": True,
         "model_version": "model-a", "prompt_version": "p1", "metrics": {"faithfulness": 0.95}},
        {"experiment_id": "baseline", "target": "evidenceflow", "score": 0.92, "passed": True,
         "model_version": "model-a", "prompt_version": "p1", "metrics": {"faithfulness": 0.9}},
        {"experiment_id": "candidate", "target": "evidenceflow", "score": 0.85, "passed": False,
         "model_version": "model-b", "prompt_version": "p2", "metrics": {"faithfulness": 0.7}},
    ]
    result = compare_experiments(runs, target="evidenceflow", baseline_experiment_id="baseline")
    candidate = next(item for item in result["experiments"] if item["experiment_id"] == "candidate")
    assert candidate["score_delta"] == -0.06
    assert candidate["metric_deltas"]["faithfulness"] == -0.225
    assert "faithfulness" in candidate["regressions"]


def test_experiment_comparison_rejects_unknown_grouping_fields():
    with pytest.raises(ValueError):
        compare_experiments([], group_by=("raw_prompt",))



def test_flowpilot_replay_dataset_covers_agent_tool_trajectory():
    case = next(
        item for item in load_cases("flowpilot")
        if item["id"] == "agent_tool_trajectory_success"
    )
    result = evaluate_case(
        "flowpilot",
        case["id"],
        case["expected"],
        case["actual"],
        mode="replay",
    )
    assert result.passed
    assert result.metrics["tool_selection_f1"] == 1.0
    assert result.metrics["tool_argument_accuracy"] == 1.0
    assert result.metrics["tool_trajectory_similarity"] == 1.0
