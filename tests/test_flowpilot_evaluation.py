import json
from pathlib import Path

from evals.project_evals import evaluate_case
from evals.project_runner import load_cases


def test_flowpilot_replay_fixtures_cover_all_workflows_and_pass():
    cases = load_cases("flowpilot")
    assert {case["expected"]["workflow"] for case in cases} == {
        "content", "competitor", "outreach", "kpi"
    }

    for case in cases:
        result = evaluate_case(
            "flowpilot",
            case["id"],
            case["expected"],
            case["actual"],
            mode="replay",
        )
        assert result.passed, (case["id"], result.metrics, result.gate_failures)


def test_flowpilot_evaluation_fails_unsafe_outreach_and_incomplete_content():
    expected = {
        "workflow": "outreach",
        "expected_candidates": ["Partner A"],
        "required_output_fields": ["candidates"],
    }
    actual = {
        "workflow": "outreach",
        "status": "completed",
        "output": {
            "candidates": [{
                "name": "Partner A",
                "message": "Draft",
                "approval_required": False,
            }]
        },
    }
    result = evaluate_case("flowpilot", "unsafe-outreach", expected, actual, mode="replay")
    assert not result.passed
    assert result.metrics["policy_compliance"] == 0.0


def test_flowpilot_evaluation_flags_missing_kpi_risks():
    expected = {
        "workflow": "kpi",
        "expected_risk_entities": ["Team A"],
        "required_output_fields": ["normalized_updates", "risks"],
    }
    actual = {
        "workflow": "kpi",
        "status": "completed",
        "output": {
            "normalized_updates": [{"entity": "Team A", "status": "at_risk"}],
            "risks": [],
            "risk_count": 0,
        },
    }
    result = evaluate_case("flowpilot", "missing-risk", expected, actual, mode="replay")
    assert result.metrics["workflow_correctness"] < 1.0
    assert not result.passed
