# Deployment

The harness is a single Render web service defined in `render.yaml`. It serves its read-only dashboard at `/` and its JSON API from the same host.

## Render environment

Configure these variables on the Evaluation Harness service:

- `DATABASE_URL`: managed PostgreSQL connection string for durable event/evaluation history. Without it, the service falls back to local SQLite.
- `DB_SCHEMA=harness`.
- `HUB_API_KEY`: private operator key for manually triggering replay evaluation.
- `HARNESS_INGEST_TOKENS_JSON`: JSON object with two distinct private values, one for `evidenceflow` and one for `quotesense`.

Generate two independent random values locally:

```bash
openssl rand -hex 32
openssl rand -hex 32
```

Set the values only in Render environment settings. Do not commit secrets.

## EvidenceFlow and QuoteSense environment

On each application service configure:

```text
EVALUATION_HARNESS_URL=https://ai-engineering-evaluation-harness.onrender.com
EVALUATION_HARNESS_INGEST_TOKEN=<that application's own token>
```

The token must match its project entry in `HARNESS_INGEST_TOKENS_JSON`. Do not reuse the same token for both apps.

The reporting client has a short timeout and treats delivery as best-effort. If the service or credentials are unavailable, the original app request continues normally.

## Website link

The agency website's `/evaluation` page links to:

`https://ai-engineering-evaluation-harness.onrender.com`

No BYOK credentials, provider keys or operator tokens are sent to the browser. The dashboard is read-only; replay writes are operator-authenticated.

## Local run

```bash
cp .env.example .env
docker compose up --build
```

The dashboard will be available at `http://localhost:8000`.
