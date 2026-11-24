# Deployment

The service is a small shared Engineering Assurance API and read-only dashboard. The website remains the public front door; this is supporting infrastructure, not a portfolio application workspace.

## Render topology

The root `render.yaml` defines one web service:

- `ai-engineering-evaluation-harness` — FastAPI health/readiness, read-only dashboard, replay-quality API, and bounded application-event ingestion.

It does not provision PostgreSQL. Configure a managed database on Render for persistent event and replay history. Without a persistent `DATABASE_URL`, the application may use local SQLite storage, which is not durable across instance replacement.

## Environment

Configure:

- `DATABASE_URL` — recommended managed PostgreSQL connection string.
- `DB_SCHEMA=harness`.
- `HUB_API_KEY` — optional operator key for manually triggering replay evaluation.
- `HARNESS_INGEST_TOKENS_JSON` — JSON object with two distinct private values for `evidenceflow` and `quotesense`.

Generate independent random values locally:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

Set the values only in hosting environment settings. Do not commit secrets.

## Connected applications

On EvidenceFlow and QuoteSense respectively, configure:

```text
EVALUATION_HARNESS_URL=https://ai-engineering-evaluation-harness.onrender.com
EVALUATION_HARNESS_INGEST_TOKEN=<matching project-specific token>
```

The application clients send only bounded, content-free run metadata and numeric metrics. Telemetry is best-effort: missing tokens or a temporarily unavailable harness must not prevent the application workflow from completing.

## Live verification boundary

The following checks were captured during the current repository audit:

- `/health` returned service status `ok`, version `4.0.0`.
- `/ready` returned `ready` with database status `ok`.
- `/api/application-summary` returned HTTP 200 data, but showed **zero live events** for both EvidenceFlow and QuoteSense.
- `/api/ai-quality` returned stored replay-fixture runs for the two retained targets. These are synthetic reference measurements, not current live model accuracy or production application outcomes.
- The root page HTML loaded, but its browser-side data widget displayed `Failed to fetch` in the inspection session even though the JSON APIs responded. Normal-browser dashboard hydration should be checked separately.

Therefore, the harness service is live and its API is ready, but real application telemetry ingestion and ordinary-browser hydration are not yet verified.

## Local development

```bash
cp .env.example .env
docker compose up --build
```

The local dashboard is available at `http://localhost:8000`.
