# Application telemetry

The Engineering Assurance dashboard separates four evidence classes so that a runtime count is never mistaken for a framework judge score:

- **Replay evaluation:** deterministic, fixture-based scores for retrieval/citation, document extraction/validation and workflow policy quality.
- **External framework scores:** normalized scores emitted by an explicitly configured evaluator and namespaced as external.<framework>.<metric>.
- **Runtime/domain checks:** numeric and boolean signals computed by the application itself, such as citation coverage, procurement reconciliation, workflow completion and approval compliance.
- **Application activity:** run completion/failure metadata used for aggregate activity and recent-run views.

## Current project emitters

- **EvidenceFlow:** reports content-free runtime/citation/grounding/guardrail/evidence metrics. Optional RAGAS faithfulness and context-precision evaluation is disabled by default and runs only when explicitly enabled with EVALUATION_RAGAS_ENABLED=true.
- **QuoteSense:** reports deterministic extraction, validation, scoring coverage, cost comparability, line-item comparability, price reconciliation, risk and anomaly checks. These are not LLM-as-a-judge scores.
- **FlowPilot:** reports workflow completion, step coverage, validation, approval compliance, pending approval, audit traceability and warning counts. It does not fabricate generic agent/tool trajectory scores when those traces are not emitted.

The harness can import normalized scalar scores from RAGAS, DeepEval, TruLens and Phoenix. DeepEval, TruLens and Phoenix are not currently runtime emitters in the connected application projects.

## Dashboard behavior

The dashboard provides project and evaluator filters, metric search, explicit framework coverage status, version lineage, experiment grouping and baseline comparisons. External scores and native runtime metrics remain separate. The comparison UI presents signed deltas; it does not assume that every negative delta is harmful because metric direction depends on semantics (for example, fewer risk findings may be desirable).

## Accepted event fields

- project: evidenceflow, quotesense or flowpilot.
- event_type and status.
- workflow: short workflow identifier.
- duration_ms: optional bounded duration.
- model: optional non-secret model label.
- request_id: optional correlation identifier.
- experiment_id, dataset_version, prompt_version, model_version, config_version: optional bounded version labels.
- metrics: up to 24 numeric/boolean values with short identifier names.

Event IDs are idempotent, allowing a sender to retry without duplicating the same event.

## Explicitly excluded

Do not send prompts, user questions, answers, conversation transcripts, uploaded files, document text, extracted quotation values, supplier/customer names, source excerpts, provider keys, Gateway tokens or stack traces. The API rejects additional payload fields and non-numeric metric values. The read-only dashboard uses only metadata and scalar metrics.

## Failure behavior

Connected app clients are best-effort: they use bounded request timeouts, swallow telemetry transport failures and do not interrupt the original application operation. Missing URL/token configuration disables reporting without disabling EvidenceFlow, QuoteSense or FlowPilot. Optional evaluator failures must not alter the response shown to the user.
