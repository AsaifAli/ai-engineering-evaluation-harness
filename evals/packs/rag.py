from __future__ import annotations

from typing import Any

from .base import EvalPack
from ..integrations.framework_scores import normalize_framework_scores
from ..metrics import (
    citation_completeness, citation_correctness, contextual_precision_at_k,
    contextual_relevance, context_recall, ndcg_at_k, precision_at_k,
    recall_at_k, reciprocal_rank,
)


def evaluate(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, float]:
    retrieved = actual.get("retrieved_documents", [])
    relevant = expected.get("relevant_documents", [])
    k = int(expected.get("k", 5))
    if k < 1:
        raise ValueError("RAG evaluation k must be positive")
    metrics = {
        f"precision@{k}": precision_at_k(retrieved, relevant, k),
        f"recall@{k}": recall_at_k(retrieved, relevant, k),
        "mrr": reciprocal_rank(retrieved, relevant),
        f"ndcg@{k}": ndcg_at_k(retrieved, relevant, k),
        f"contextual_precision@{k}": contextual_precision_at_k(retrieved, relevant, k),
        "context_recall": context_recall(retrieved, relevant),
        "contextual_relevance": contextual_relevance(retrieved, relevant),
        "citation_completeness": citation_completeness(
            actual.get("citations", []), expected.get("required_citations", relevant)
        ),
        "citation_correctness": citation_correctness(
            actual.get("citations", []), expected.get("relevant_citations", relevant)
        ),
        "answer_relevance": float(actual.get("answer_relevance", 0.0)),
        "faithfulness": float(actual.get("faithfulness", actual.get("groundedness", 0.0))),
        "groundedness": float(actual.get("groundedness", actual.get("faithfulness", 0.0))),
    }
    metrics.update(normalize_framework_scores(actual.get("framework_scores", {})))
    for name, score in metrics.items():
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"RAG metric {name} must be between 0 and 1")
    return {name: round(score, 6) for name, score in metrics.items()}


PACK = EvalPack(
    name="rag",
    evaluator=evaluate,
    gates={
        "recall@5": 0.80,
        "contextual_precision@5": 0.70,
        "mrr": 0.80,
        "citation_correctness": 0.95,
        "faithfulness": 0.85,
    },
    weights={
        "precision@5": 0.07,
        "recall@5": 0.12,
        "mrr": 0.07,
        "ndcg@5": 0.08,
        "contextual_precision@5": 0.10,
        "context_recall": 0.10,
        "contextual_relevance": 0.06,
        "citation_completeness": 0.10,
        "citation_correctness": 0.10,
        "answer_relevance": 0.10,
        "faithfulness": 0.10,
    },
    description="Retriever and generator quality: ranking, context precision/recall/relevance, citations, answer relevance and faithfulness.",
    tags=("retrieval", "ragas-aligned", "deepeval-aligned", "grounding", "citations"),
)
