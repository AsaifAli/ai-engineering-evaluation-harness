import math

from evals.metrics import (
    average_precision_at_k,
    citation_completeness,
    citation_correctness,
    contextual_precision_at_k,
    contextual_relevance,
    context_recall,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    token_f1,
)
from evals.project_evals import evaluate_case


def test_ranking_metrics():
    retrieved = ["d1", "noise", "d2", "d2"]
    relevant = ["d1", "d2"]
    assert precision_at_k(retrieved, relevant, 3) == 0.666667
    assert recall_at_k(retrieved, relevant, 3) == 1.0
    assert reciprocal_rank(retrieved, relevant) == 1.0
    assert average_precision_at_k(retrieved, relevant, 3) == 0.833333
    assert ndcg_at_k(retrieved, relevant, 3) > 0.9


def test_context_and_citation_metrics():
    retrieved = ["relevant-a", "noise", "relevant-b"]
    relevant = ["relevant-a", "relevant-b"]
    assert contextual_precision_at_k(retrieved, relevant, 3) == 0.833333
    assert contextual_relevance(retrieved, relevant) == 0.666667
    assert context_recall(retrieved, relevant) == 1.0
    assert citation_completeness(["a"], ["a", "b"]) == 0.5
    assert citation_correctness(["a", "wrong"], ["a"]) == 0.5


def test_rag_pack_adds_ragas_and_deepeval_aligned_metrics():
    result = evaluate_case(
        "evidenceflow",
        "rag-framework-coverage",
        {
            "k": 5,
            "relevant_documents": ["d1", "d2"],
            "required_citations": ["d1"],
            "relevant_citations": ["d1", "d2"],
        },
        {
            "retrieved_documents": ["d1", "noise", "d2"],
            "citations": ["d1"],
            "answer_relevance": 0.9,
            "groundedness": 0.95,
        },
        mode="replay",
    )
    assert result.metrics["context_recall"] == 1.0
    assert result.metrics["faithfulness"] == 0.95
    assert "contextual_precision@5" in result.metrics
    assert "contextual_relevance" in result.metrics
