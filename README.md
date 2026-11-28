# AI Engineering Studio — Engineering Assurance

A small internal evaluation and observability service for the studio's three connected application references:

- **EvidenceFlow** — retrieval, evidence and answer-quality evaluation.
- **QuoteSense** — structured extraction, validation and procurement decision-quality evaluation.
- **FlowPilot** — workflow completion, approval policy, retry recovery and execution-state evaluation.

The agency website remains the public front door. This service is a read-only engineering assurance view for visitors and a private telemetry intake for the three applications. It is not a standalone SaaS product, and it does not request or store BYOK credentials.

## What stays

- Project-specific replay evaluation against versioned synthetic fixtures.
- Quality gates and metric history for EvidenceFlow, QuoteSense and FlowPilot.
- Application event intake for bounded run metadata and numeric quality signals from all three projects.
- Event history, success/failure counts and average run duration.
- A read-only dashboard at `/`.

## What was intentionally removed from the active service

The runtime no longer starts or exposes MLOps registries, model promotion, n8n orchestration, external-project adapters, five-project fleet polling, LLM-as-a-judge, issue triage or PR-review automation. The service has no model-provider connection and does not trigger application runs.

Legacy database tables are left untouched when upgrading an existing database. New deployments create only the tables needed for application events, replay quality results and the audit record attached to evaluation batches.


## Evaluation framework coverage

The default evaluation path remains deterministic and provider-free. EvidenceFlow's RAG pack reports retriever and generator dimensions separately:

- Retriever: Precision@K, Recall@K, MRR, NDCG@K, reference-labelled contextual precision, context recall and context relevance.
- Evidence: citation completeness and citation correctness.
- Generator: answer relevance and faithfulness/groundedness.
- Other applications retain their specialist evaluation packs: QuoteSense document extraction/decision quality and FlowPilot approval, retry and execution-state integrity.

Replay fixture values for answer relevance and faithfulness are supplied reference signals, not live LLM-judge results. Contextual metrics in deterministic replay are computed against labelled relevant document IDs. They should not be confused with semantic LLM-judged RAGAS/DeepEval metrics.

### Optional RAGAS and DeepEval adapters

Third-party frameworks are supported as opt-in evaluator dependencies, not mandatory dependencies of the production dashboard. The harness does not instantiate provider clients, read provider API keys, or make external model calls. The calling application must configure a model/evaluator and explicitly invoke the adapter.

```bash
pip install -e ".[eval-ragas]"       # RAGAS only
pip install -e ".[eval-deepeval]"    # DeepEval only
pip install -e ".[eval-all]"         # both
```

RAGAS 0.4+ (async collections API):

```python
from evals.frameworks import evaluate_with_ragas_async

scores = await evaluate_with_ragas_async(
    {
        "user_input": "What is the retention period?",
        "response": "Records are kept for seven years.",
        "retrieved_contexts": ["The retention policy specifies seven years."],
        "reference": "Records are retained for seven years.",
    },
    llm=my_configured_ragas_llm,
    embeddings=my_configured_embeddings,
)
```

DeepEval:

```python
from evals.frameworks import evaluate_with_deepeval

scores = evaluate_with_deepeval(
    {
        "input": "What is the retention period?",
        "actual_output": "Records are kept for seven years.",
        "expected_output": "Records are retained for seven years.",
        "retrieval_context": ["The retention policy specifies seven years."],
    },
    metrics=my_configured_deepeval_metrics,
)
```

Only pass synthetic or appropriately redacted samples to external judges. Do not transmit customer documents, chat transcripts, prompts, or business data without a privacy and data-processing review. Framework scores are returned to the caller and are not mixed into replay history or live application-event telemetry automatically.

Further reading: [RAGAS metrics](https://docs.ragas.io/en/latest/concepts/metrics/available_metrics/), [RAGAS 0.4 migration](https://docs.ragas.io/en/stable/howtos/migrations/migrate_from_v03_to_v04/), [DeepEval RAG evaluation](https://deepeval.com/docs/getting-started-rag), [TruLens RAG Triad](https://github.com/truera/trulens/blob/main/docs/getting_started/core_concepts/rag_triad.md).

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

```bash
PYTHONPATH=. python -m evals.project_runner --target all --mode replay
```

Run tests:

```bash
PYTHONPATH=. python -m pytest -q
```

Replay results are reference measurements against synthetic fixtures. They are not live model benchmarks, customer data or client outcome claims.

### TruLens and Phoenix score imports; Claude boundary

TruLens and Arize Phoenix can export bounded scalar evaluation scores into the replay fixture `actual.framework_scores` field. Their runtime packages are not installed or invoked by this service. Imported scores are namespaced observations and do not alter existing gates or composite scores automatically. See `docs/AI_EVALUATION.md` for the accepted metric names and validation rules.

Claude Managed Agents and Claude Agent SDK execution, sessions and Claude-specific tool/trace capture remain in the Claude runtime adapter. This harness evaluates only sanitized, provider-neutral outcomes exported by that layer; Agency OS retains authority over permissions, budgets, approvals, business state and audit.
