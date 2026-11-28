# AI Engineering Studio — Engineering Assurance

A small internal evaluation and observability service for the studio's three connected application references:

- **EvidenceFlow** — retrieval, evidence and answer-quality evaluation.
- **QuoteSense** — structured extraction, validation and procurement decision-quality evaluation.
- **FlowPilot** — workflow completion, approval policy, retry recovery and execution-state evaluation.

The agency website remains the public front door. This service is a read-only engineering assurance view for visitors and a private telemetry intake for the three applications. It is not a standalone SaaS product, and it does not request or store BYOK credentials.

## What stays

- Project-specific replay evaluation against versioned synthetic fixtures.
- Quality gates and metric history for EvidenceFlow, QuoteSense and FlowPilot.
- Deterministic retrieval metrics plus bounded, offline score imports from Ragas, DeepEval, TruLens and Arize Phoenix.
- Application event intake for bounded run metadata and numeric quality signals from all three projects.
- Event history, success/failure counts and average run duration.
- A read-only dashboard at `/`.

## What was intentionally removed from the active service

The runtime no longer starts or exposes MLOps registries, model promotion, n8n orchestration, external-project adapters, five-project fleet polling, LLM-as-a-judge, issue triage or PR-review automation. The service has no model-provider connection and does not trigger application runs.

Legacy database tables are left untouched when upgrading an existing database. New deployments create only the tables needed for application events, replay quality results and the audit record attached to evaluation batches.

## Dashboard

The Render service URL is:

`https://ai-engineering-evaluation-harness.onrender.com`

The dashboard is intentionally read-only and does not require a provider key or user login. It shows the latest replay evaluation evidence separately from real application activity so fixture-based measurements are not confused with live application performance.

## API

| Endpoint | Purpose | Access |
|---|---|---|
| `GET /health` | Liveness | Public |
| `GET /ready` | Database readiness | Public |
| `GET /` | Read-only client dashboard | Public |
| `GET /api/ai-quality` | Latest replay evaluation results | Public |
| `POST /api/ai-quality/run?target=all` | Trigger replay evaluation | Operator bearer key |
| `POST /api/application-events` | Receive app metadata | Project-specific bearer token |
| `GET /api/application-events` | Recent event history | Public, metadata only |
| `GET /api/application-summary` | Aggregated app activity | Public, metadata only |

### Event contract

Each connected project can send an event with:

- Project slug: `evidenceflow`, `quotesense` or `flowpilot`.
- Event type and status.
- A short workflow identifier and optional request ID.
- Duration and optional model label.
- Up to 24 numeric/boolean metrics.

The payload schema rejects unknown fields. Do not send user prompts, chat transcripts, uploaded documents, extracted quotation content, source excerpts, model responses, provider keys, gateway tokens or other customer/business data. Event IDs are idempotent to make retries safe.

## Configuration

The harness uses a distinct ingestion token per application. Generate three independent random values, for example:

```bash
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 32
```

Set these environment variables on the Render services:

**Evaluation Harness**
- `DATABASE_URL` — managed PostgreSQL URL for persistence. Without it, the service uses local SQLite.
- `HUB_API_KEY` — operator-only key for manually triggering replay evaluation.
- `HARNESS_INGEST_TOKENS_JSON` — legacy JSON object mapping project slugs to distinct tokens.
- `HARNESS_EVIDENCEFLOW_INGEST_TOKEN`, `HARNESS_QUOTESENSE_INGEST_TOKEN`, and `HARNESS_FLOWPILOT_INGEST_TOKEN` — optional per-project credentials. When set, a dedicated variable takes precedence over that project's entry in the legacy JSON map. This allows rotating or adding one integration without reading or replacing other write-only Render secrets.

**EvidenceFlow, QuoteSense and FlowPilot**
- `EVALUATION_HARNESS_URL=https://ai-engineering-evaluation-harness.onrender.com`
- `EVALUATION_HARNESS_INGEST_TOKEN` — the token matching that application's dedicated harness setting.

Keep tokens only in hosting environment settings. Never commit them or expose them with a `NEXT_PUBLIC_` variable. Telemetry delivery is best-effort: an unavailable harness must never stop a user workflow.

## Local development

```bash
cp .env.example .env
docker compose up --build
```

Open `http://localhost:8000`.

Run the deterministic quality fixtures:

```PYTHONPATH=. python -m evals.project_runner --target all --mode replay```

Run tests:

```PYTHONPATH=. python -m pytest -q```

Replay results are reference measurements against synthetic fixtures. They are not live model benchmarks, customer data or client outcome claims. Framework interoperability imports already-computed scalar scores only; the service does not execute external frameworks or LLM judges. See `docs/AI_EVALUATION.md`.
