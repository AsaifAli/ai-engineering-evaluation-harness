# Application telemetry

The dashboard separates two types of evidence:

- **Replay evaluation**: deterministic fixture scores for retrieval/citation and document-extraction/business-rule quality.
- **Application activity**: run completion/failure metadata reported by EvidenceFlow and QuoteSense.

This separation is intentional. Synthetic replay checks should never be described as live model performance.

## Accepted event fields

- `project`: `evidenceflow` or `quotesense`.
- `event_type` and `status`.
- `workflow`: short workflow identifier.
- `duration_ms`: optional bounded duration.
- `model`: optional non-secret model label.
- `request_id`: optional correlation identifier.
- `metrics`: up to 24 numeric/boolean values with short identifier names.

Event IDs are idempotent, allowing a sender to retry without duplicating the same event.

## Explicitly excluded

Do not send prompts, user questions, answers, conversation transcripts, uploaded files, document text, extracted quotation values, supplier/customer names, source excerpts, provider keys, Gateway tokens or stack traces. The API rejects additional payload fields and non-numeric metric values.

## Failure behavior

The two app clients are best-effort: they use a short request timeout, swallow telemetry transport failures and do not interrupt the original application operation. Missing URL/token configuration disables reporting without disabling EvidenceFlow or QuoteSense.
