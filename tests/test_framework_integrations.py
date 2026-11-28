import pytest

from evals.integrations.framework_scores import normalize_framework_scores
from evals.packs.rag import evaluate


def test_normalizes_supported_framework_scores_without_running_a_judge():
    scores = normalize_framework_scores(
        {
            "ragas": {"faithfulness": 0.91, "answer_relevancy": {"score": 0.87}},
            "deepeval": {"FaithfulnessMetric": 0.89, "ContextualRecallMetric": 0.8},
            "trulens": {"groundedness": 0.92, "answer_relevance": 0.88},
            "phoenix": {"retrieval_relevance": 0.86, "faithfulness": 0.9},
        }
    )

    assert scores == {
        "external.ragas.faithfulness": 0.91,
        "external.ragas.answer_relevancy": 0.87,
        "external.deepeval.faithfulness": 0.89,
        "external.deepeval.context_recall": 0.8,
        "external.trulens.groundedness": 0.92,
        "external.trulens.answer_relevancy": 0.88,
        "external.phoenix.context_relevancy": 0.86,
        "external.phoenix.faithfulness": 0.9,
    }


def test_rejects_unknown_frameworks_and_metrics():
    with pytest.raises(ValueError, match="unsupported evaluation framework"):
        normalize_framework_scores({"unknown": {"faithfulness": 0.9}})
    with pytest.raises(ValueError, match="unsupported metric"):
        normalize_framework_scores({"ragas": {"made_up_metric": 0.9}})


@pytest.mark.parametrize("score", [-0.1, 1.1, float("nan"), float("inf"), "0.9"])
def test_rejects_invalid_external_scores(score):
    with pytest.raises(ValueError):
        normalize_framework_scores({"ragas": {"faithfulness": score}})


def test_rag_pack_computes_rank_aware_context_metrics_and_imports_external_scores():
    metrics = evaluate(
        {"k": 3, "relevant_documents": ["d1", "d3"]},
        {
            "retrieved_documents": ["d2", "d1", "d3"],
            "framework_scores": {"ragas": {"faithfulness": 0.94}},
        },
    )

    assert metrics["contextual_precision@3"] == pytest.approx(0.583333, abs=1e-6)
    assert metrics["context_recall"] == 1.0
    assert metrics["contextual_relevance"] == pytest.approx(2 / 3, abs=1e-6)
    assert metrics["external.ragas.faithfulness"] == 0.94


def test_rag_pack_does_not_invent_llm_judge_scores_when_missing():
    metrics = evaluate(
        {"k": 3, "relevant_documents": ["d1"]},
        {"retrieved_documents": ["d1"]},
    )

    assert "external.ragas.faithfulness" not in metrics
    # The core pack keeps its deterministic 0.0 baseline; no external judge score is fabricated.\n    assert metrics["faithfulness"] == 0.0\n    assert "external.ragas.faithfulness" not in metrics


def test_external_framework_scores_are_observations_not_implicit_gate_inputs():
    from evals.project_evals import evaluate_case

    baseline = evaluate_case(
        "evidenceflow",
        "case",
        {"k": 3, "relevant_documents": ["d1"]},
        {"retrieved_documents": ["d1"], "answer_relevance": 0.9, "groundedness": 0.9},
        mode="replay",
    )
    imported = evaluate_case(
        "evidenceflow",
        "case",
        {"k": 3, "relevant_documents": ["d1"]},
        {
            "retrieved_documents": ["d1"],
            "answer_relevance": 0.9,
            "groundedness": 0.9,
            "framework_scores": {"ragas": {"faithfulness": 0.01}},
        },
        mode="replay",
    )

    assert imported.score == baseline.score
    assert imported.passed == baseline.passed
    assert imported.metrics["external.ragas.faithfulness"] == 0.01


def test_accepts_current_ragas_camel_case_metric_names():
    scores = normalize_framework_scores(
        {"ragas": {"ResponseRelevancy": 0.91, "ContextPrecision": 0.82, "AgentGoalAccuracy": 1.0}}
    )
    assert scores == {
        "external.ragas.answer_relevancy": 0.91,
        "external.ragas.context_precision": 0.82,
        "external.ragas.agent_goal_accuracy": 1.0,
    }
