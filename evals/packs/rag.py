from __future__ import annotations

from typing import Any

from .base import EvalPack
from ..metrics import average_precision_at_k, citation_completeness, citation_correctness, ndcg_at_k, precision_at_k, recall_at_k, reciprocal_rank


def evaluate(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, float]:
    retrieved = actual.get("retrieved_documents", [])
    relevant = expected.get("relevant_documents", [])
    k = int(expected.get("k", 5))
    metrics = {
        f"recall@{k}": recall_at_k(retrieved, relevant, k),
        f"precision@{k}": precision_at_k(retrieved, relevant, k),
        "mrr": reciprocal_rank(retrieved, relevant),
        f"map@{k}": average_precision_at_k(retrieved, relevant, k),
        f"ndcg@{k}": ndcg_at_k(retrieved, relevant, k),
        "citation_completeness": citation_completeness(actual.get("citations", []), expected.get("required_citations", relevant)),
        "citation_correctness": citation_correctness(actual.get("citations", []), expected.get("relevant_citations", relevant)),
        "answer_relevance": float(actual.get("answer_relevance", 0.0)),
        "groundedness": float(actual.get("groundedness", 0.0)),
    }
    return {key: round(value, 6) for key, value in metrics.items()}


PACK = EvalPack(
    name="rag",
    evaluator=evaluate,
    gates={"recall@5": 0.80, "mrr": 0.80, "ndcg@5": 0.75, "citation_correctness": 0.95, "groundedness": 0.85},
    weights={"recall@5": 0.15, "precision@5": 0.10, "mrr": 0.10, "map@5": 0.10, "ndcg@5": 0.10, "citation_completeness": 0.10, "citation_correctness": 0.10, "answer_relevance": 0.10, "groundedness": 0.15},
    description="Retrieval, citation and grounded-answer quality for RAG systems.",
    tags=("retrieval", "grounding", "citations"),
)
