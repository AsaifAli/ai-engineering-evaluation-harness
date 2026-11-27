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