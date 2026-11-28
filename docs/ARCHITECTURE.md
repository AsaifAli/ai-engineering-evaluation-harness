# Engineering Assurance architecture

The agency website remains the public front door. The Evaluation Harness is a small internal service with two responsibilities:

1. Store deterministic replay-evaluation results for EvidenceFlow and QuoteSense.
2. Receive bounded, privacy-safe application activity metadata from those two deployed services.

```text
AI Engineering Studio website
       |
       +---- link to read-only Engineering Assurance dashboard
                                      |
                                      v
                        AI Engineering Evaluation Service
                          |                     |
                 Replay evaluator       Application event API
                   /         \              /        \
            EvidenceFlow   QuoteSense  EvidenceFlow  QuoteSense
                fixtures    fixtures     telemetry    telemetry
```

## Application boundary

EvidenceFlow and QuoteSense keep their own ingestion, orchestration, provider, retrieval, validation and business logic. They send one short event after a run completes or fails. Delivery is best-effort and must never block an app workflow.

The harness receives only the project slug, event type/status, workflow label, duration, optional model label, request identifier and a small set of numeric/boolean metrics. It does not receive prompts, answers, uploaded documents, extracted quotation fields, supplier names, source excerpts, provider keys or Gateway session tokens.

## Authentication boundary

- Dashboard and read-only application summaries are public.
- Each app has a different bearer token and may submit events only for its own project slug.
- An operator bearer key gates manually triggered replay evaluations.
- No model-provider connection or BYOK configuration exists in the harness.

## Storage

The active service creates only application-event, replay-quality and evaluation-audit tables. Existing legacy tables are not dropped during an upgrade. Replay results remain distinct from app-reported runtime events so synthetic checks are not confused with live product performance.

## Evaluation framework and Claude boundary

RAGAS and DeepEval can be explicitly invoked through optional adapters using caller-configured evaluator instances. TruLens and Phoenix results can be imported as allowlisted scalar scores without adding their runtimes to the service. No framework result import receives raw prompts, answers, contexts, traces or credentials; imported scores are namespaced and do not change gates implicitly.

Claude Managed Agents/Agent SDK execution and Claude-specific session/tool traces belong to the Claude runtime adapter. Only sanitized, provider-neutral evaluation outcomes may cross into this service. Agency OS retains authority over execution permissions, budgets, approvals, business state and audit.
