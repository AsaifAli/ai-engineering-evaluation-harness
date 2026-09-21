from __future__ import annotations

import math
from typing import Any, Iterable, Sequence


def _unique(values: Iterable[Any]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        token = str(value)
        if token not in seen:
            seen.add(token)
            out.append(token)
    return out


def precision_at_k(retrieved: Sequence[Any], relevant: Iterable[Any], k: int) -> float:
    if k <= 0:
        return 0.0
    rel = set(_unique(relevant))
    ranked = _unique(retrieved)[:k]
    return round(sum(item in rel for item in ranked) / k, 6)


def recall_at_k(retrieved: Sequence[Any], relevant: Iterable[Any], k: int) -> float:
    if k <= 0:
        return 0.0
    rel = set(_unique(relevant))
    if not rel:
        return 1.0
    ranked = _unique(retrieved)[:k]
    return round(sum(item in rel for item in ranked) / len(rel), 6)


def reciprocal_rank(retrieved: Sequence[Any], relevant: Iterable[Any]) -> float:
    rel = set(_unique(relevant))
    if not rel:
        return 1.0
    for index, item in enumerate(_unique(retrieved), start=1):
        if item in rel:
            return round(1.0 / index, 6)
    return 0.0


def average_precision_at_k(retrieved: Sequence[Any], relevant: Iterable[Any], k: int) -> float:
    rel = set(_unique(relevant))
    if not rel:
        return 1.0
    ranked = _unique(retrieved)[:k]
    hits = 0
    score = 0.0
    for index, item in enumerate(ranked, start=1):
        if item in rel:
            hits += 1
            score += hits / index
    return round(score / min(len(rel), k), 6) if hits else 0.0


def _dcg(retrieved: Sequence[Any], relevant: set[str], k: int) -> float:
    score = 0.0
    for index, item in enumerate(_unique(retrieved)[:k], start=1):
        if item in relevant:
            score += 1.0 / math.log2(index + 1)
    return score


def ndcg_at_k(retrieved: Sequence[Any], relevant: Iterable[Any], k: int) -> float:
    rel = set(_unique(relevant))
    if not rel:
        return 1.0
    ideal = list(rel)
    ideal_dcg = _dcg(ideal, rel, min(k, len(ideal)))
    if ideal_dcg == 0:
        return 0.0
    return round(_dcg(retrieved, rel, k) / ideal_dcg, 6)


def exact_match(predicted: Any, expected: Any) -> float:
    return 1.0 if predicted == expected else 0.0


def token_f1(predicted: str, expected: str) -> float:
    pred = str(predicted or "").lower().split()
    gold = str(expected or "").lower().split()
    if not pred and not gold:
        return 1.0
    if not pred or not gold:
        return 0.0
    pred_counts: dict[str, int] = {}
    gold_counts: dict[str, int] = {}
    for token in pred:
        pred_counts[token] = pred_counts.get(token, 0) + 1
    for token in gold:
        gold_counts[token] = gold_counts.get(token, 0) + 1
    overlap = sum(min(pred_counts.get(token, 0), count) for token, count in gold_counts.items())
    if overlap == 0:
        return 0.0
    precision = overlap / len(pred)
    recall = overlap / len(gold)
    return round(2 * precision * recall / (precision + recall), 6)


def classification_metrics(y_true: Sequence[Any], y_pred: Sequence[Any], labels: Iterable[Any] | None = None) -> dict[str, float]:
    labels_set = set(labels or list(y_true) + list(y_pred))
    if not labels_set:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0, "accuracy": 1.0}
    per_class: list[tuple[float, float, float]] = []
    for label in labels_set:
        tp = sum(a == label and b == label for a, b in zip(y_true, y_pred))
        fp = sum(a != label and b == label for a, b in zip(y_true, y_pred))
        fn = sum(a == label and b != label for a, b in zip(y_true, y_pred))
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class.append((precision, recall, f1))
    n = len(per_class)
    accuracy = sum(a == b for a, b in zip(y_true, y_pred)) / max(1, len(y_true))
    return {
        "precision": round(sum(x[0] for x in per_class) / n, 6),
        "recall": round(sum(x[1] for x in per_class) / n, 6),
        "f1": round(sum(x[2] for x in per_class) / n, 6),
        "accuracy": round(accuracy, 6),
    }


def set_precision_recall_f1(predicted: Iterable[Any], expected: Iterable[Any]) -> dict[str, float]:
    pred = set(_unique(predicted))
    gold = set(_unique(expected))
    if not pred and not gold:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    intersection = len(pred & gold)
    precision = intersection / len(pred) if pred else 0.0
    recall = intersection / len(gold) if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 6), "recall": round(recall, 6), "f1": round(f1, 6)}


def citation_completeness(citations: Iterable[Any], required_sources: Iterable[Any]) -> float:
    return recall_at_k(list(citations), list(required_sources), max(1, len(set(map(str, required_sources)))))


def citation_correctness(citations: Iterable[Any], relevant_sources: Iterable[Any]) -> float:
    required = set(_unique(relevant_sources))
    actual = _unique(citations)
    if not actual:
        return 1.0 if not required else 0.0
    return round(sum(item in required for item in actual) / len(actual), 6)


def claim_support(claims: Iterable[str], contexts: Iterable[str]) -> float:
    context_tokens = set()
    for context in contexts:
        context_tokens.update(str(context).lower().split())
    claims_list = list(claims)
    if not claims_list:
        return 1.0
    supported = 0
    for claim in claims_list:
        tokens = [t for t in str(claim).lower().split() if len(t) > 3]
        if tokens and sum(token in context_tokens for token in tokens) / len(tokens) >= 0.5:
            supported += 1
    return round(supported / len(claims_list), 6)


def mean(values: Iterable[float]) -> float:
    items = list(values)
    return round(sum(items) / len(items), 6) if items else 0.0
