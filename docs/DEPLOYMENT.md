# Deployment

## Local

```bash
cp .env.example .env
docker compose up --build
```

API/dashboard: http://localhost:8000
n8n: http://localhost:5678

## API deployment on Render

The repository contains `render.yaml` for the FastAPI service. Connect the GitHub repository in Render and deploy the `ai-engineering-automation-api` service. The free service is suitable for a portfolio demo, but SQLite data is ephemeral on free web instances; use managed Postgres or a persistent disk for durable production audit history.

## n8n deployment

For the public n8n instance, use n8n Cloud or a managed/container host with persistent storage. Set:

- `N8N_ENCRYPTION_KEY`
- `N8N_HOST`
- `N8N_PROTOCOL=https`
- `WEBHOOK_URL=https://<your-n8n-host>/`
- persistent `/home/node/.n8n` storage or Postgres

After importing the four workflows, replace the internal API URL `http://api:8000` with the public FastAPI URL when n8n is hosted separately.

## GitHub webhook

Create a webhook on a test repository pointing to:

`https://<your-n8n-host>/webhook/ai-issue-triage`

and/or

`https://<your-n8n-host>/webhook/ai-pr-review`

Use GitHub's JSON payload and subscribe to Issues and Pull requests. Start with a test repository and keep write actions behind approval.

## Production hardening

- Use Postgres instead of SQLite.
- Put n8n behind HTTPS.
- Store secrets in the hosting provider's secret manager.
- Restrict GitHub token permissions to the minimum required.
- Add webhook signature verification.
- Use separate credentials for read and write actions.
- Keep external GitHub mutations behind human approval until the workflow is trusted.
