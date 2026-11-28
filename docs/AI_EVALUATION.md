# Project-specific replay evaluation

The active evaluator supports three connected agency applications, each with a domain-specific pack:

- **EvidenceFlow** uses the rag pack for retrieval ranking, evidence and grounded answers.
- **QuoteSense** uses the document_intelligence pack for structured extraction, validation and procurement decision quality.
- **FlowPilot** uses the workflow_orchestration pack for workflow completion, required-step coverage, human approval enforcement, retry recovery, state integrity, error classification and audit traceability.

Evaluation runs use small, synthetic, version-controlled fixtures. They are deterministic reference checks, not live model benchmarks, production accuracy claims or client outcome measurements.

## EvidenceFlow: retrieval and evidence quality

Metrics include Recall@K, Precision@K, MRR, MAP@K, nDCG@K, citation completeness/correctness, answer relevance and groundedness.

## QuoteSense: document and decision quality

Metrics include field exact match, critical-field accuracy, schema validity, numeric accuracy, risk classification F1 and recommendation consistency.

## FlowPilot: workflow orchestration and guardrails

Metrics include workflow completion, required-step coverage, approval compliance before external-impact actions, retry recovery within the configured attempt limit, valid persisted state transitions, error classification accuracy and audit traceability. Replay fixtures exercise the policy contract without calling a live provider or publishing/sending anything.

## Run the fixtures

PYTHONPATH=. python -m evals.project_runner --target all --mode replay


Run one application:

PYTHONPATH=. python -m evals.project_runner --target evidenceflow --mode replay
PYTHONPATH=. python -m evals.project_runner --target quotesense --mode replay
PYTHONPATH=. python -m evals.project_runner --target flowpilot --mode replay


Results are stored by batch and exposed through GET /api/ai-quality. Public quality and activity APIs allowlist only these three current application references. Historical rows for retired projects remain in the database but are filtered from the client-facing snapshot.
## Additional framework result interoperability

The active `evals.frameworks` module provides opt-in execution adapters for RAGAS 0.4+ and DeepEval using caller-configured evaluator/model instances. The harness also provides a dependency-free score-import boundary for bounded scalar results from RAGAS, DeepEval, TruLens and Arize Phoenix. A replay fixture may include `actual.framework_scores` shaped as `{framework: {metric_name: score}}` (or `{ "score": number }`). Imported scores must be finite numeric values in [0, 1], and framework/metric names are allowlisted and namespaced as `external.<framework>.<canonical_metric>`.

TruLens and Phoenix are score-import integrations only in this repository; their runtime/evaluator packages are not installed or invoked here. RAGAS/DeepEval judge execution remains opt-in through `evals.frameworks`, with caller-owned model and embedding configuration. The dashboard service itself remains provider-free. Imported framework results are observations: they do not alter the composite score or release gates unless a separately reviewed pack change explicitly opts them in.

Claude Managed Agents and Claude Agent SDK sessions, tool execution, model calls and Claude-specific trace capture remain in the Claude runtime adapter. This harness can evaluate only sanitized, provider-neutral outcomes exported by that layer. It must not create Claude sessions, invoke Claude tools, own runtime credentials or become another agent orchestrator. Agency OS remains authoritative for permissions, budgets, approvals, business state and audit.


## Runtime evaluation reporting

Connected applications may send a separate `evaluation.completed` event after an explicitly enabled evaluator finishes. The event schema accepts only bounded numeric metrics and optional model/prompt/dataset/config version labels; the event cannot carry prompts, answers, retrieved passages, documents, agent traces or provider credentials.

Optional lineage fields are:

- `experiment_id`
- `dataset_version`
- `prompt_version`
- `model_version`
- `config_version`

Example (scores only):

```json
{
  "project": "evidenceflow",
  "event_type": "evaluation.completed",
  "status": "success",
  "workflow": "rag_query",
  "experiment_id": "support-rag-model-b-prompt-v4",
  "dataset_version": "support-synthetic-v2",
  "prompt_version": "synthesis-v4",
  "model_version": "provider/model-b",
  "config_version": "retrieval-v3",
  "metrics": {
    "external.ragas.faithfulness": 0.94,
    "external.ragas.answer_relevancy": 0.91,
    "external.ragas.context_precision": 0.88
  }
}
```

The runtime reporting endpoints are read-only:

- `GET /api/ai-quality/runtime?limit=60&project=evidenceflow` — per-run scores and aggregates.
- `GET /api/ai-quality/runtime-experiments?target=evidenceflow&baseline_experiment_id=baseline` — model/prompt/dataset lineage comparisons and per-metric deltas.

The dashboard displays runtime evaluator results separately from deterministic replay evidence and ordinary application activity. A missing result means no connected application has reported an evaluation event; it must not be interpreted as a zero score. Metric deltas are compared only when the same metric exists in both experiment groups. No synthetic composite score is inferred from unrelated metrics.

Database upgrades add nullable lineage columns to the existing application-events table and preserve historical rows. Existing application event producers remain compatible because all lineage fields are optional.
