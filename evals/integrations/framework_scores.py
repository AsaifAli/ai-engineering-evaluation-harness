from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any


# These are intentionally score-import adapters, not framework runtimes. The
# frameworks own judge/model execution; this service validates and stores only
# bounded scalar results supplied by an authorized evaluation process.
_METRIC_ALIASES: dict[str, dict[str, str]] = {
    "ragas": {
        "faithfulness": "faithfulness",
        "answer_relevancy": "answer_relevancy",
        "response_relevancy": "answer_relevancy",
        "responserelevancy": "answer_relevancy",
        "context_precision": "context_precision",
        "contextprecision": "context_precision",
        "context_recall": "context_recall",
        "contextrecall": "context_recall",
        "context_entity_recall": "context_entity_recall",
        "contextentitiesrecall": "context_entity_recall",
        "noise_sensitivity": "noise_sensitivity",
        "noisesensitivity": "noise_sensitivity",
        "factual_correctness": "factual_correctness",
        "factualcorrectness": "factual_correctness",
        "answer_correctness": "factual_correctness",
        "tool_call_accuracy": "tool_call_accuracy",
        "toolcallaccuracy": "tool_call_accuracy",
        "tool_call_f1": "tool_call_f1",
        "toolcallf1": "tool_call_f1",
        "agent_goal_accuracy": "agent_goal_accuracy",
        "agentgoalaccuracy": "agent_goal_accuracy",
    },
    "deepeval": {
        "faithfulnessmetric": "faithfulness",
        "answerrelevancymetric": "answer_relevancy",
        "contextualrelevancymetric": "context_relevancy",
        "contextualprecisionmetric": "context_precision",
        "contextualrecallmetric": "context_recall",
    },
    "trulens": {
        "groundedness": "groundedness",
        "context_relevance": "context_relevancy",
        "answer_relevance": "answer_relevancy",
    },
    "phoenix": {
        "faithfulness": "faithfulness",
        "retrieval_relevance": "context_relevancy",
        "correctness": "correctness",
        "completeness": "completeness",
    },
}


def normalize_framework_scores(payload: Mapping[str, Any]) -> dict[str, float]:
    """Validate and namespace scores exported by supported evaluation frameworks.

    Input shape: ``{framework: {metric_name: score | {"score": score}}}``.
    Scores must already be normalized to [0, 1]. No prompts, contexts, model
    outputs, credentials, or framework execution objects are accepted here.
    """
    if not isinstance(payload, Mapping):
        raise ValueError("framework scores must be an object")
    normalized: dict[str, float] = {}
    for framework, metrics in payload.items():
        framework_name = str(framework).strip().lower()
        if framework_name not in _METRIC_ALIASES:
            raise ValueError(f"unsupported evaluation framework: {framework_name}")
        if not isinstance(metrics, Mapping):
            raise ValueError(f"metrics for {framework_name} must be an object")
        for raw_name, raw_score in metrics.items():
            metric_name = str(raw_name).strip().lower()
            canonical = _METRIC_ALIASES[framework_name].get(metric_name)
            if canonical is None:
                raise ValueError(f"unsupported metric for {framework_name}: {metric_name}")
            if isinstance(raw_score, Mapping):
                if set(raw_score) != {"score"}:
                    raise ValueError("metric result objects may contain only a score")
                raw_score = raw_score["score"]
            if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)):
                raise ValueError("framework metric scores must be numeric")
            score = float(raw_score)
            if not math.isfinite(score) or not 0.0 <= score <= 1.0:
                raise ValueError("framework metric scores must be finite values between 0 and 1")
            key = f"external.{framework_name}.{canonical}"
            if key in normalized:
                raise ValueError(f"duplicate normalized framework metric: {key}")
            normalized[key] = round(score, 6)
            if len(normalized) > 48:
                raise ValueError("at most 48 external framework scores may be imported")
    return normalized
