from __future__ import annotations

import math
from collections import Counter
from typing import Any, Iterable, Sequence


def _stable_unique(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value)
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def precision_at_k(retrieved: Sequence[Any], relevant: Iterable[Any], k: int) -> float:
    if k <= 0:
        return 0.0
    truth = set(_stable_unique(relevant))
    ranked = _stable_unique(retrieved)[:k]
    return round(sum(item in truth for item in ranked) / k, 6)


def recall_at_k(retrieved: Sequence[Any], relevant: Iterable[Any], k: int) -> float:
    truth = set(_stable_unique(relevant))
    if not truth:
        return 1.0
    return round(sum(item in truth for item in _stable_unique(retrieved)[:max(0, k)]) / len(truth), 6)


def reciprocal_rank(retrieved: Sequence[Any], relevant: Iterable[Any]) -> float:
    truth = set(_stable_unique(relevant))
    if not truth:
        return 1.0
    for rank, item in enumerate(_stable_unique(retrieved), 1):
        if item in truth:
            return round(1.0 / rank, 6)
    return 0.0


def average_precision_at_k(retrieved: Sequence[Any], relevant: Iterable[Any], k: int) -> float:
    truth = set(_stable_unique(relevant))
    if not truth:
        return 1.0
    ranked = _stable_unique(retrieved)[:max(0, k)]
    hits = 0
    total = 0.0
    for rank, item in enumerate(ranked, 1):
        if item in truth:
            hits += 1
            total += hits / rank
    denominator = min(len(truth), max(0, k))
    return round(total / denominator, 6) if denominator else 0.0


def ndcg_at_k(retrieved: Sequence[Any], relevant: Iterable[Any], k: int) -> float:
    truth = set(_stable_unique(relevant))
    if not truth:
        return 1.0

    def dcg(items: Sequence[Any]) -> float:
        return sum(
            1.0 / math.log2(rank + 1)
            for rank, item in enumerate(items[:max(0, k)], 1)
            if str(item) in truth
        )

    ideal = dcg(list(truth))
    return round(dcg(_stable_unique(retrieved)) / ideal, 6) if ideal else 0.0


def contextual_precision_at_k(retrieved: Sequence[Any], relevant: Iterable[Any], k: int) -> float:
    truth = set(_stable_unique(relevant))
    if not truth:
        return 1.0
    hits = 0
    weighted = 0.0
    for rank, item in enumerate(_stable_unique(retrieved)[:max(0, k)], 1):
        if item in truth:
            hits += 1
            weighted += hits / rank
    denominator = min(len(truth), max(0, k))
    return round(weighted / denominator, 6) if denominator else 0.0


def contextual_relevance(retrieved: Sequence[Any], relevant: Iterable[Any]) -> float:
    ranked = _stable_unique(retrieved)
    if not ranked:
        return 1.0
    truth = set(_stable_unique(relevant))
    return round(sum(item in truth for item in ranked) / len(ranked), 6)


def context_recall(retrieved: Sequence[Any], relevant: Iterable[Any]) -> float:
    return recall_at_k(retrieved, relevant, len(_stable_unique(retrieved)))


def citation_completeness(citations: Iterable[Any], required_sources: Iterable[Any]) -> float:
    required = _stable_unique(required_sources)
    return recall_at_k(list(citations), required, len(required))


def citation_correctness(citations: Iterable[Any], relevant_sources: Iterable[Any]) -> float:
    expected = set(_stable_unique(relevant_sources))
    actual = _stable_unique(citations)
    if not actual:
        return 1.0 if not expected else 0.0
    return round(sum(item in expected for item in actual) / len(actual), 6)


def exact_match(predicted: Any, expected: Any) -> float:
    return 1.0 if predicted == expected else 0.0


def token_f1(predicted: str, expected: str) -> float:
    pred = Counter(str(predicted or "").lower().split())
    gold = Counter(str(expected or "").lower().split())
    if not pred and not gold:
        return 1.0
    overlap = sum((pred & gold).values())
    if not overlap:
        return 0.0
    precision = overlap / sum(pred.values())
    recall = overlap / sum(gold.values())
    return round(2 * precision * recall / (precision + recall), 6)


def mean(values: Iterable[float]) -> float:
    items = list(values)
    return round(sum(items) / len(items), 6) if items else 0.0
