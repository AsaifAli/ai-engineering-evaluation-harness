# AI quality evaluation layer

The harness now has two distinct evaluation layers.

1. **Deterministic harness validation** checks that the control-plane endpoints, guardrails, structured outputs and fallback paths behave correctly.
2. **Project-specific AI quality evaluation** measures the quality dimensions that matter for each portfolio system. These evaluations can run in replay mode today and can consume live normalized outputs when a target execution API is available.

## Metric contract by project

### EvidenceFlow — RAG / research

The evaluator supports retrieval and answer-quality measurements:

- Recall@K — fraction of relevant evidence retrieved in the top K results.
- Precision@K — relevance density in the top K results.
- MRR — how early the first relevant result appears.
- MAP@K — ranking quality across all relevant results.
- nDCG@K — graded ranking quality with position discounting.
- Citation completeness — required sources that are cited.
- Citation correctness — cited sources that are actually relevant.
- Answer relevance and groundedness — normalized quality signals supplied by the project adapter/evaluation fixture.

This is the layer to extend with a larger golden corpus and, where available, direct EvidenceFlow retrieval traces.

### LegacyLens — software modernization

- transformation success
- syntax/compile pass rate
- unit-test pass rate
- semantic verification pass rate
- release-gate pass rate
- changed-file precision/recall/F1 via file-set overlap

The key idea is that successful text generation alone is not considered a successful migration; executable validation is required.

### QuoteSense — document / procurement intelligence

- field exact-match accuracy
- critical-field accuracy
- schema validity
- numeric extraction accuracy
- risk classification accuracy/F1
- recommendation consistency

Critical fields should be weighted more heavily than non-critical metadata in a larger production benchmark.

### WebQA Intelligence — browser testing

- test-generation precision/recall/F1
- defect-detection precision/recall
- regression-detection precision/recall
- locator validity
- execution success

This lets the harness distinguish between generating many tests and generating tests that actually cover the known behaviors and defects.

### FlowPilot — agentic workflow execution

- task success
- step success
- tool-call validity
- policy/guardrail pass rate
- approval compliance
- execution reliability
- fallback-free rate

The harness also records latency, provider/model, token usage and cost metadata for live AI runs.

## Golden-set and replay model

Every project has a small versioned fixture under `evals/datasets/`. Replay results are explicitly marked as **reference measurements**, not production LLM quality claims. This keeps the dashboard honest while still proving the complete evaluation machinery.

A real project adapter can replace the fixture's `actual` object with a normalized live response without changing the metric engine.

## Quality gates and regression

Each workload type has reusable metric thresholds in `evals/packs/`; targets reference an evaluation pack rather than owning the metric implementation. A case fails its target gate when one or more critical metrics fall below the threshold. Runs are grouped into a batch so the platform compares a complete evaluation batch against the previous batch for the same target.

The n8n workflow `06_ai_quality_regression_gate.json` demonstrates scheduled quality evaluation, policy checking and regression event recording.

## What not to claim

Do not put the replay values on a resume or present them as measured production model performance. The portfolio story is the engineering capability: metric design, golden-set management, project adapters, automated gates, persistence, regression tracking and operationalization.


## Reusable evaluation packs

Evaluation logic is separated from project adapters. The built-in packs are `rag`, `agent_workflow`, `code_modernization`, `document_intelligence` and `browser_qa`. This means a new AI service can reuse a workload-specific metric contract without copying evaluation code into that service.
