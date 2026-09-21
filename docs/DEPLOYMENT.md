# Deployment

## Render

The repository includes `render.yaml` for the FastAPI service.

Set the gateway session variables in Render rather than committing them. The project defaults to deterministic mode until `LLM_PROVIDER=gateway` is explicitly enabled.

## n8n

Run n8n on a persistent n8n deployment or n8n Cloud. Import the workflow JSON files and replace the placeholder HTTP URLs/credentials with the deployed API endpoint and your GitHub integration.

## Persistence

The sample uses SQLite for portability. For a long-lived multi-instance deployment, use a managed relational database and migrate the storage layer before relying on historical telemetry as the source of truth.

## Five-project target health

For the live fleet-health workflow, configure the five registered target URLs in the API service environment:

```text
COMMAND_CENTER_BASE_URL=https://ai-automation-api.onrender.com
LEGACY_LENS_BASE_URL=https://ai-code-modernization-api.onrender.com
EVIDENCEFLOW_BASE_URL=https://evidenceflow-langgraph.onrender.com
QUOTESENSE_BASE_URL=https://quotation-analyzer.onrender.com
WEBQA_BASE_URL=https://web-crawler-agent.onrender.com
```

The `/api/targets/health` endpoint then checks all five services. n8n workflow `07_five_project_fleet_health.json` schedules that fleet check and records the resulting health state in the Hub audit stream.
