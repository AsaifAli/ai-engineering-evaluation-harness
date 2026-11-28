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
    if metrics is not None:
        configured = list(metrics)
        if not configured:
            raise ValueError("At least one RAGAS metric must be configured")
        return configured
    try:
        from ragas.metrics import collections as ragas_collections
    except ImportError as exc:
        raise RuntimeError("Install the optional extra: pip install -e '.[eval-ragas]'") from exc
    if llm is None:
        raise ValueError("Pass a caller-configured RAGAS LLM or explicit metric instances")

    def resolve(*names: str):
        for name in names:
            metric_type = getattr(ragas_collections, name, None)
            if metric_type is not None:
                return metric_type
        raise RuntimeError(
            "Installed RAGAS version is missing the expected metric class: " + " or ".join(names)
        )

    has_reference = sample.get("reference") is not None
    constructors = [
        resolve("Faithfulness"),
        resolve("AnswerRelevancy"),
    ]
    if has_reference:
        constructors.extend([
            resolve("ContextPrecisionWithReference", "ContextPrecision"),
            resolve("ContextRecall"),
            resolve("AnswerCorrectness"),
        ])
    else:
        constructors.append(
            resolve("ContextPrecisionWithoutReference", "ContextUtilization")
        )
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



async def evaluate_ragas_dataset(
    samples: Iterable[dict[str, Any]],
    *,
    metrics: Iterable[Any] | None = None,
    llm: Any = None,
    embeddings: Any = None,
) -> dict[str, Any]:
    """Score a batch of live RAG samples with RAGAS and return aggregate metrics.

    Each sample uses the RAGAS collections schema: user_input, response,
    retrieved_contexts, and optional reference/reference_contexts. The optional
    id field is retained only as a result label and is never sent to a metric.
    The caller owns model configuration, network access, data handling and costs.
    """
    batch = list(samples)
    if not batch:
        return {
            "framework": "ragas",
            "sample_count": 0,
            "results": [],
            "summary": {"metrics": {}},
        }

    required_fields = {"user_input", "response", "retrieved_contexts"}
    prepared: list[tuple[str, dict[str, Any]]] = []
    for index, sample in enumerate(batch, start=1):
        if not isinstance(sample, dict):
            raise ValueError(f"RAGAS sample {index} must be an object")
        missing = sorted(required_fields - set(sample))
        if missing:
            raise ValueError(f"RAGAS sample {index} is missing required fields: {', '.join(missing)}")
        if not isinstance(sample["user_input"], str) or not isinstance(sample["response"], str):
            raise ValueError(f"RAGAS sample {index} user_input and response must be strings")
        contexts = sample["retrieved_contexts"]
        if not isinstance(contexts, list) or any(not isinstance(item, str) for item in contexts):
            raise ValueError(f"RAGAS sample {index} retrieved_contexts must be a list of strings")
        if "reference" in sample and sample["reference"] is not None and not isinstance(sample["reference"], str):
            raise ValueError(f"RAGAS sample {index} reference must be a string")
        case_id = str(sample.get("id") or f"case-{index}")
        payload = {key: value for key, value in sample.items() if key not in {"id", "metadata"}}
        prepared.append((case_id, payload))

    reference_presence = [payload.get("reference") is not None for _, payload in prepared]
    if any(reference_presence) and not all(reference_presence):
        raise ValueError("RAGAS samples must consistently include reference or omit it")
    metric_instances = _ragas_metrics(prepared[0][1], llm, embeddings, metrics)
    case_results: list[dict[str, Any]] = []
    aggregates: dict[str, list[float]] = {}
    for case_id, payload in prepared:
        scores: dict[str, Any] = {}
        for metric in metric_instances:
            name = str(getattr(metric, "name", None) or metric.__class__.__name__)
            score = await metric.ascore(**payload)
            normalized = _normalize_result(score)
            scores[name] = normalized
            aggregates.setdefault(name, []).append(normalized["score"])
        case_results.append({"case_id": case_id, "metrics": scores})

    summary = {
        name: {
            "mean": round(sum(values) / len(values), 6),
            "min": round(min(values), 6),
            "max": round(max(values), 6),
            "samples": len(values),
        }
        for name, values in sorted(aggregates.items())
        if values
    }
    return {
        "framework": "ragas",
        "sample_count": len(case_results),
        "results": case_results,
        "summary": {"metrics": summary},
    }


def _to_deepeval_tool_calls(values: Any, *, field_name: str, tool_call_type: Any) -> list[Any]:
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list")
    converted = []
    for index, value in enumerate(values, start=1):
        if isinstance(value, str):
            name = value.strip()
            kwargs: dict[str, Any] = {"name": name}
        elif isinstance(value, dict):
            name = str(value.get("name") or value.get("tool") or value.get("tool_name") or "").strip()
            if not name:
                raise ValueError(f"{field_name}[{index}] is missing a tool name")
            kwargs = {"name": name}
            description = value.get("description")
            if description is not None:
                kwargs["description"] = str(description)
            tool_input = value.get("input", value.get("arguments"))
            if tool_input is not None:
                kwargs["input"] = tool_input
            if "output" in value:
                kwargs["output"] = value["output"]
        else:
            raise ValueError(f"{field_name}[{index}] must be a string or object")
        if not name:
            raise ValueError(f"{field_name}[{index}] has an empty tool name")
        converted.append(tool_call_type(**kwargs))
    return converted


def evaluate_agent_tools_with_deepeval(
    sample: dict[str, Any],
    *,
    metrics: Iterable[Any] | None = None,
) -> dict[str, Any]:
    """Evaluate tool selection and argument decisions using explicit DeepEval metrics.

    Sample fields: input, actual_output, tool_calls and expected_tool_calls.
    Pass ToolCorrectnessMetric / ArgumentCorrectnessMetric instances configured
    with the desired judge model. No default model or credential lookup occurs.
    """
    if metrics is None:
        raise ValueError(
            "Pass explicitly configured DeepEval metric instances; implicit default models are disabled"
        )
    configured_metrics = list(metrics)
    if not configured_metrics:
        raise ValueError("At least one explicitly configured DeepEval metric is required")
    try:
        from deepeval.test_case import LLMTestCase, ToolCall
    except ImportError as exc:
        raise RuntimeError("Install the optional extra: pip install -e '.[eval-deepeval]'") from exc

    for field in ("input", "actual_output"):
        if not isinstance(sample.get(field), str):
            raise ValueError(f"DeepEval agent sample {field} must be a string")
    tools_called = _to_deepeval_tool_calls(
        sample.get("tool_calls", []),
        field_name="tool_calls",
        tool_call_type=ToolCall,
    )
    expected_tools = _to_deepeval_tool_calls(
        sample.get("expected_tool_calls", []),
        field_name="expected_tool_calls",
        tool_call_type=ToolCall,
    )
    test_case = LLMTestCase(
        input=sample["input"],
        actual_output=sample["actual_output"],
        tools_called=tools_called,
        expected_tools=expected_tools,
    )

    results: dict[str, Any] = {}
    for metric in configured_metrics:
        metric.measure(test_case)
        normalized = _normalize_result(metric.score)
        normalized["reason"] = getattr(metric, "reason", normalized.get("reason"))
        normalized["success"] = getattr(metric, "success", None)
        results[metric.__class__.__name__] = normalized
    return results
