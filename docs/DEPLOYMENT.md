# Deployment

## Render

The repository includes `render.yaml` for the FastAPI service.

Set the gateway session variables in Render rather than committing them. The project defaults to deterministic mode until `LLM_PROVIDER=gateway` is explicitly enabled.

## n8n

Run n8n on a persistent n8n deployment or n8n Cloud. Import the workflow JSON files and replace the placeholder HTTP URLs/credentials with the deployed API endpoint and your GitHub integration.

## Persistence

The sample uses SQLite for portability. For a long-lived multi-instance deployment, use a managed relational database and migrate the storage layer before relying on historical telemetry as the source of truth.
