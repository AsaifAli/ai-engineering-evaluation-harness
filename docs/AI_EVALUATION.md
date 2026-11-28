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
## Framework interoperability (score import, not framework execution)

The harness now includes a dependency-free score-import boundary for results produced by:

- **Ragas**: faithfulness, answer/response relevancy, context precision/recall, context entity recall, noise sensitivity, factual correctness, and selected agent/tool metrics.
- **DeepEval**: faithfulness, answer relevancy, contextual relevancy, contextual precision and contextual recall.
- **TruLens**: groundedness, context relevance and answer relevance.
- **Arize Phoenix**: faithfulness, retrieval relevance, correctness and completeness.

A replay fixture may optionally include an `actual.framework_scores` object, shaped as `{framework: {metric_name: score}}`. A metric may also be represented as `{ "score": number }`. Imported values must be finite numbers in the inclusive range 0–1; unknown frameworks/metrics, duplicate aliases, non-numeric values and oversized imports are rejected. Stored names are namespaced as `external.<framework>.<canonical_metric>`.

This is intentionally an interoperability layer, not an embedded Ragas/DeepEval/TruLens/Phoenix runtime. The harness does not invoke LLM judges, embeddings, providers, or remote evaluation services; it does not receive prompts, answers, contexts or trace payloads. Third-party tools execute in their separately authorized environment and may export bounded scores for offline replay ingestion. Imported framework scores are observations only: they do not silently change the existing composite score or quality gates. Gate changes require an explicit reviewed change to the pack configuration and supporting fixtures.

The RAG pack additionally computes deterministic, relevance-label-based `context_precision@K` (rank-aware average precision), `context_recall@K`, and `context_relevancy@K`. These do not claim to replace judge-based semantic metrics such as faithfulness or answer relevancy. No semantic score is fabricated when an external evaluator has not supplied one.

## Claude and agent-runtime boundary

Claude Managed Agents and Claude Agent SDK execution, session state, tool execution, model calls, and Claude-specific trace capture remain in the Claude runtime adapter/integration layer. This harness may evaluate provider-neutral, sanitized outcomes (for example, goal completion, tool-call correctness, trajectory quality, and policy-compliance scores) after that layer exports them. It must not create Claude sessions, invoke Claude tools, own runtime credentials, or become a second agent orchestrator. Agency OS remains authoritative for permissions, budgets, approvals, business state and audit records.
