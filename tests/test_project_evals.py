from evals.metrics import ndcg_at_k, recall_at_k, reciprocal_rank
from evals.project_evals import evaluate_case


def test_retrieval_metrics_are_real_information_retrieval_metrics():
    ranked = ["d2", "d1", "d9", "d4", "d8"]
    relevant = ["d1", "d2"]
    assert recall_at_k(ranked, relevant, 5) == 1.0
    assert reciprocal_rank(ranked, relevant) == 1.0
    assert ndcg_at_k(ranked, relevant, 5) > 0.9


def test_evidenceflow_quality_gate():
    result = evaluate_case(
        "evidenceflow",
        "t1",
        {"k": 5, "relevant_documents": ["d1"], "required_citations": ["d1"], "relevant_citations": ["d1"]},
        {"retrieved_documents": ["d1", "d2"], "citations": ["d1"], "answer_relevance": 0.95, "groundedness": 0.95},
        mode="replay",
    )
    assert result.passed
    assert result.metrics["recall@5"] == 1.0


def test_quotesense_structured_document_quality_gate():
    result = evaluate_case(
        "quotesense",
        "t1",
        {
            "fields": {"supplier": "Example Vendor", "total_cost": 1200},
            "critical_fields": ["supplier", "total_cost"],
            "risk_label": "low",
        },
        {
            "fields": {"supplier": "Example Vendor", "total_cost": 1200},
            "schema_valid": True,
            "numeric_accuracy": 1.0,
            "risk_label": "low",
            "recommendation_consistency": 1.0,
        },
        mode="replay",
    )
    assert result.passed
    assert result.metrics["field_exact_match"] == 1.0
    assert result.metrics["schema_validity"] == 1.0


def test_flowpilot_approval_retry_and_state_quality_gate():
    expected = {
        "terminal_status": "completed",
        "recovery_terminal_status": "completed",
        "required_steps": ["execute", "validate", "approval_requested", "approval_granted", "completed"],
        "approval_required": True,
        "retry_expected": True,
        "max_attempts": 3,
        "failure_code": "provider_rate_limited",
    }
    actual = {
        "status": "completed",
        "completed_steps": ["execute", "validate", "approval_requested", "approval_granted", "completed"],
        "approval_recorded": True,
        "approved": True,
        "external_action_executed": True,
        "attempts": 2,
        "state_transitions": ["queued", "running", "retry_wait", "running", "awaiting_approval", "completed"],
        "state_persisted": True,
        "audit_recorded": True,
        "failure_code": "provider_rate_limited",
    }
    result = evaluate_case("flowpilot", "approval-retry", expected, actual, mode="replay")
    assert result.passed
    assert result.metrics["approval_compliance"] == 1.0
    assert result.metrics["retry_recovery"] == 1.0
    assert result.metrics["state_integrity"] == 1.0


def test_flowpilot_blocks_unapproved_external_actions():
    expected = {
        "terminal_status": "awaiting_approval",
        "required_steps": ["execute", "validate", "approval_requested"],
        "approval_required": True,
        "max_attempts": 1,
    }
    actual = {
        "status": "awaiting_approval",
        "completed_steps": ["execute", "validate", "approval_requested"],
        "approval_recorded": True,
        "approved": False,
        "external_action_executed": True,
        "attempts": 1,
        "state_transitions": ["queued", "running", "awaiting_approval"],
        "state_persisted": True,
        "audit_recorded": True,
    }
    result = evaluate_case("flowpilot", "approval-violation", expected, actual, mode="replay")
    assert not result.passed
    assert "approval_compliance<1.0" in result.gate_failures
