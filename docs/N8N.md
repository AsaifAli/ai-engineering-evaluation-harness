# n8n orchestration

n8n is used as the external orchestration layer rather than duplicating workflow scheduling and integration logic inside FastAPI.

Included workflows:

1. GitHub issue -> AI triage -> approval creation
2. GitHub PR -> AI review -> approval creation
3. Scheduled experiment digest -> deterministic comparison -> approval
4. Approval decision webhook -> persist decision and audit event
5. LLM health monitor -> policy check -> alert path
6. Scheduled five-project AI quality evaluation -> quality gate -> regression event
7. Scheduled five-project fleet health -> live target health fan-out -> fleet health audit event

The five-project fleet workflow uses the Hub target registry as the integration boundary: n8n calls `/api/targets/health`, and FastAPI fans the request out to the five registered project health surfaces. The quality workflow remains replay-based so benchmark results are deterministic and are not presented as live model performance.

The pattern is intentionally simple:

```text
Trigger / schedule
      -> HTTP call into FastAPI
      -> deterministic policy / AI service
      -> human approval or quality gate
      -> audit event / external notification
```

Import the JSON files under `workflows/` into a local n8n instance. The URLs target the Docker Compose API service (`http://api:8000`) so the workflows can run inside the same Compose network.
