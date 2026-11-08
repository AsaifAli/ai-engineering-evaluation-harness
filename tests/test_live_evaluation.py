from app.harness import AgentRun
from evals.trajectory import evaluate_live_trajectory


def make_run(output, metadata=None, trace=None, status="completed"):
    return AgentRun(
        run_id="live-123",
        workflow="migration",
        status=status,
        output=output,
        duration_ms=2500,
        trace=trace or [],
        metadata=metadata or {},
    )


def make_quality_gate(
    *,
    release_ready=True,
    quality_score=92.0,
    semantic_status="verified",
    check_statuses=("passed", "passed"),
):
    return {
        "status": "passed" if release_ready else "blocked",
        "release_ready": release_ready,
        "quality_score": quality_score,
        "checks": [
            {
                "name": f"check-{index}",
                "required": True,
                "status": check_status,
            }
            for index, check_status in enumerate(check_statuses)
        ],
        "semantic_gate": {
            "status": "passed" if semantic_status == "verified" else "blocked",
            "semantic_status": semantic_status,
        },
        "repair_history": [],
    }


def test_actual_legacy_response_produces_live_score():
    gate = make_quality_gate()

    run = make_run({
        "status": "ready",
        "release_ready": True,
        "quality_gate": gate,
        "semantic_verification": {"status": "verified"},
    })

    result = evaluate_live_trajectory("legacylens", run)

    assert result["evaluation_status"] == "complete"
    assert result["passed"] is True
    assert result["score"] == 0.92
    assert result["score_percent"] == 92.0
    assert result["metrics"]["required_check_pass_rate"] == 1.0
    assert result["metrics"]["semantic_verification"] == 1.0
    assert result["metrics"]["release_gate"] == 1.0
    assert result["missing_required_metrics"] == []


def test_blocked_release_is_complete_but_fails():
    gate = make_quality_gate(
        release_ready=False,
        quality_score=70.0,
        check_statuses=("passed", "failed"),
    )

    run = make_run({
        "status": "blocked",
        "release_ready": False,
        "quality_gate": gate,
        "semantic_verification": {"status": "verified"},
    }, status="failed")

    result = evaluate_live_trajectory("legacylens", run)

    assert result["evaluation_status"] == "complete"
    assert result["passed"] is False
    assert result["score"] == 0.70
    assert result["metrics"]["required_check_pass_rate"] == 0.5
    assert "required_check_pass_rate<1.0" in result["gate_failures"]
    assert "release_gate<1.0" in result["gate_failures"]


def test_missing_semantic_evidence_withholds_score():
    gate = make_quality_gate()
    gate.pop("semantic_gate")

    run = make_run({
        "status": "ready",
        "release_ready": True,
        "quality_gate": gate,
    })

    result = evaluate_live_trajectory("legacylens", run)

    assert result["evaluation_status"] == "incomplete"
    assert result["score"] is None
    assert result["passed"] is None
    assert result["missing_required_metrics"] == ["semantic_verification"]
    assert "semantic_verification" in result["unavailable_metrics"]


def test_unavailable_required_check_is_not_counted_as_passed():
    gate = make_quality_gate(check_statuses=("passed", "unavailable"))

    run = make_run({
        "status": "blocked",
        "release_ready": False,
        "quality_gate": gate,
        "semantic_verification": {"status": "verified"},
    })

    result = evaluate_live_trajectory("legacylens", run)

    assert result["evaluation_status"] == "complete"
    assert result["metrics"]["required_check_pass_rate"] == 0.5
    assert result["native_evidence"]["required_check_counts"]["unavailable"] == 1
    assert result["passed"] is False


def test_unsupported_target_returns_none():
    assert evaluate_live_trajectory("flowpilot", make_run({})) is None