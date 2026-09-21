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


def test_flowpilot_fallback_free_metric_has_correct_direction():
    result = evaluate_case(
        "flowpilot",
        "t1",
        {"required_steps": ["a"], "success_statuses": ["completed"]},
        {"status": "completed", "completed_steps": ["a"], "tool_call_validity": 1.0, "policy_pass_rate": 1.0, "approval_compliant": True, "execution_reliability": 1.0, "fallback_rate": 0.0},
        mode="replay",
    )
    assert result.metrics["fallback_free_rate"] == 1.0


def test_experiment_comparison_detects_regression():
    from evals.experiments import compare_batches
    from app.db import insert_ai_quality
    baseline_batch = "baseline-test"
    candidate_batch = "candidate-test"
    insert_ai_quality(batch_id=baseline_batch, target="evidenceflow", case_id="c1", mode="replay", score=0.9, passed=True, metrics={"recall@5": 1.0, "ndcg@5": 0.9}, gate_failures=[], notes=[])
    insert_ai_quality(batch_id=candidate_batch, target="evidenceflow", case_id="c1", mode="replay", score=0.7, passed=True, metrics={"recall@5": 0.7, "ndcg@5": 0.9}, gate_failures=[], notes=[])
    comparison = compare_batches(target="evidenceflow", baseline_batch_id=baseline_batch, candidate_batch_id=candidate_batch)
    assert comparison["status"] == "regression"
    assert "recall@5" in comparison["regressions"]
