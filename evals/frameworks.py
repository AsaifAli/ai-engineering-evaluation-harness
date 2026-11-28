"""Optional third-party RAG evaluation adapters.

The core harness remains deterministic and provider-free. These adapters run only
when explicitly called with caller-configured evaluator/model instances. They do
not create provider clients, read API keys, or send data anywhere by themselves.
"""
from __future__ import annotations

from typing import Any, Iterable


def _normalize_result(value: Any) -> dict[str, Any]:
    if hasattr(value, "value"):
        score, reason = value.value, getattr(value, "reason", None)
    else:
        score, reason = value, None
    if score is None:
        raise ValueError("Evaluator returned no score")
    numeric = float(score)
    if not 0.0 <= numeric <= 1.0:
        raise ValueError("Evaluator scores must be normalized to [0, 1]")
    result: dict[str, Any] = {"score": round(numeric, 6)}
    if reason:
        result["reason"] = str(reason)
    return result


def _ragas_metrics(sample: dict[str, Any], llm: Any, embeddings: Any, metrics: Iterable[Any] | None):
    try:
        from ragas.metrics.collections import (
            AnswerCorrectness, AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness
        )
    except ImportError as exc:
        raise RuntimeError("Install the optional extra: pip install -e '.[eval-ragas]'") from exc
    if metrics is not None:
        return list(metrics)
    if llm is None:
        raise ValueError("Pass a caller-configured RAGAS LLM or explicit metric instances")
    constructors = [Faithfulness, AnswerRelevancy, ContextPrecision, ContextRecall]
    if sample.get("reference"):
        constructors.append(AnswerCorrectness)
    configured = []
    for constructor in constructors:
        kwargs = {"llm": llm}
        if embeddings is not None:
            kwargs["embeddings"] = embeddings
        configured.append(constructor(**kwargs))
    return configured


def evaluate_with_ragas(sample: dict[str, Any], *, metrics: Iterable[Any] | None = None,
                        llm: Any = None, embeddings: Any = None) -> dict[str, Any]:
    """Synchronous wrapper for explicitly supplied RAGAS-compatible scorers."""
    results: dict[str, Any] = {}
    for metric in _ragas_metrics(sample, llm, embeddings, metrics):
        name = getattr(metric, "name", None) or metric.__class__.__name__
        score = metric.ascore(**sample)
        if hasattr(score, "__await__"):
            raise RuntimeError("RAGAS metric returned an awaitable; use evaluate_with_ragas_async()")
        results[str(name)] = _normalize_result(score)
    return results


async def evaluate_with_ragas_async(sample: dict[str, Any], *, metrics: Iterable[Any] | None = None,
                                    llm: Any = None, embeddings: Any = None) -> dict[str, Any]:
    """Async RAGAS 0.4+ adapter using collections metrics and keyword arguments."""
    results: dict[str, Any] = {}
    for metric in _ragas_metrics(sample, llm, embeddings, metrics):
        name = getattr(metric, "name", None) or metric.__class__.__name__
        score = await metric.ascore(**sample)
        results[str(name)] = _normalize_result(score)
    return results


def evaluate_with_deepeval(sample: dict[str, Any], *,
                           metrics: Iterable[Any] | None = None) -> dict[str, Any]:
    """Evaluate one DeepEval LLMTestCase with caller-configured metrics/models."""
    if metrics is None:
        raise ValueError(
            "Pass explicitly configured DeepEval metric instances; implicit default models are disabled"
        )
    try:
        from deepeval.test_case import LLMTestCase
    except ImportError as exc:
        raise RuntimeError("Install the optional extra: pip install -e '.[eval-deepeval]'") from exc
    test_case = LLMTestCase(
        input=sample["input"],
        actual_output=sample["actual_output"],
        expected_output=sample.get("expected_output"),
        retrieval_context=sample.get("retrieval_context", []),
    )
    results: dict[str, Any] = {}
    for metric in metrics:
        metric.measure(test_case)
        results[metric.__class__.__name__] = {
            **_normalize_result(metric.score),
            "reason": getattr(metric, "reason", None),
            "success": getattr(metric, "success", None),
        }
    return results
