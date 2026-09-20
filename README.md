# AI Engineering Automation Hub

**n8n + FastAPI + LLM-ready AI services + GitHub automation + human approval + auditability**

A portfolio project designed for AI/ML engineers who need to demonstrate practical workflow automation without turning the project into a generic no-code demo.

## What it demonstrates

- Event-driven and scheduled automation with **n8n**
- Custom AI services with **Python/FastAPI**
- Structured classification, risk analysis and experiment evaluation
- GitHub webhook integration points
- Human-in-the-loop approval before external actions
- Persistent audit events and approval state
- Dockerized local environment
- CI tests with GitHub Actions
- Clean separation between **AI reasoning** and **workflow orchestration**

## Architecture

```text
                    GitHub / Scheduler / Webhook
                                |
                                v
                         +--------------+
                         |     n8n      |
                         | orchestration|
                         +------+-------+
                                |
                   HTTP / structured payloads
                                |
                         +------v-------+
                         |    FastAPI   |
                         |  AI services |
                         +------+-------+
                                |
                 +--------------+--------------+
                 |              |              |
                 v              v              v
              Triage         PR Risk       Experiment
              analysis       analysis       analysis
                 |              |              |
                 +--------------+--------------+
                                |
                                v
                        Approval + Audit DB
                                |
                                v
                      GitHub / Notifications
```

## Workflows

### 1. AI Issue Triage
GitHub issue event → n8n → normalization → AI classification → approval request → audit event.

### 2. AI PR Review Assistant
Pull request event → n8n → metadata normalization → risk analysis → approval request → audit event.

### 3. Scheduled Experiment Digest
Daily schedule → experiment metrics → baseline comparison → regression detection → approval request.

### 4. Approval Decision
Approval webhook → FastAPI decision endpoint → audit trail.

The external GitHub mutation step is intentionally kept behind approval. This makes the demo safe to run on a test repository.

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

Open:

- Dashboard/API: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`
- n8n: `http://localhost:5678`

Import the four JSON files from `workflows/` into n8n.

## API examples

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/ai/triage \
  -H 'Content-Type: application/json' \
  -d '{"title":"Production credential leaked","body":"token exposed in logs"}'
```

## Test

```bash
pip install -r requirements.txt
pytest -q
```

## Deployment

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## Important note about the AI layer

The repository ships with a deterministic fallback so the project runs without a paid LLM key. A production deployment can replace the fallback service with an OpenAI-compatible structured-output call while retaining the same n8n contracts.

## Security notes

- Never commit `.env` or tokens.
- Use least-privilege GitHub credentials.
- Verify GitHub webhook signatures before trusting production events.
- Keep write operations behind approval until the workflow has been validated.
- Use Postgres/persistent storage for production audit history.
