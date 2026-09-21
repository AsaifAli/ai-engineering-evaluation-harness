# AI Engineering Evaluation, Agent Harness & LLMOps Platform

A reusable middle layer for operating multiple AI systems. It combines **project adapters, agent harnessing, n8n orchestration, LLM observability, retrieval/task-specific evaluation, guardrails, reliability controls, human approval, regression detection, auditability and CI quality gates**.

The goal is to demonstrate the engineering layer that sits **after a prototype works**: instrument it, evaluate it, govern it, and make it safer to operate.

## What this demonstrates

- Reusable **agent harness** around existing AI applications
- Five registered portfolio AI systems with project-specific adapters
- Live adapters where stable execution APIs exist
- Replay adapters where hosted UIs do not expose stable execution APIs
- n8n for schedules, webhooks, external orchestration and quality-monitoring workflows
- LLM observability: latency, provider/model, prompt version, fallback, token and cost metadata
- AI quality evaluation with task-specific metrics rather than one generic score
- **RAG retrieval metrics including Recall@K, Precision@K, MRR, MAP@K and nDCG@K**
- Citation correctness/completeness, groundedness and answer relevance for RAG
- Code modernization validation: syntax, unit tests, semantic verification and release gates
- Document extraction validation: field accuracy, numeric accuracy, schema validity and risk F1
- Browser QA validation: test-generation F1, defect/regression detection and locator validity
- Agent/workflow validation: task success, step success, tool-call validity and approval compliance
- Golden sets, quality gates, regression deltas and persisted evaluation history
- Prompt injection handling, input sanitization and structured output validation
- Timeout/retry/circuit-breaker controls and deterministic fallback
- Human-in-the-loop approval before consequential external action
- Docker, CI and cloud-ready deployment patterns

## Five-project harness

The harness is deliberately a **middle infrastructure layer**, not a sixth business application:

```text
FlowPilot          LegacyLens          EvidenceFlow
      \                |                    /
       \               |                   /
        +------ Project Adapters ---------+
                       |
                       v
            AI Engineering Harness
        ┌─────────┬───────────┬────────────┐
        │Telemetry│ Evaluator │ Guardrails │
        │          │           │ Reliability│
        └────┬─────┴─────┬─────┴─────┬──────┘
             │           │           │
             v           v           v
           Audit     Quality Gates   HITL
             \           |           /
              +---------+-----------+
                        |
                     Dashboard
                        |
                    n8n / CI
```

| Target | Harness mode | Evaluation focus |
|---|---|---|
| **FlowPilot / AI Automation Command Center** | live + replay | workflow success, policy, approvals, reliability |
| **LegacyLens / Agentic Software Modernization** | live task + replay | syntax, tests, semantic verification, release gates |
| **EvidenceFlow / Verified Sparse-First RAG** | health + replay | Recall@K, nDCG, MRR, citations, groundedness |
| **QuoteSense / Procurement Intelligence** | health + replay | extraction accuracy, schema validity, risk classification |
| **WebQA Intelligence / AI-Assisted Testing** | health + replay | test generation, defect/regression detection, execution |

The last three are first-class targets even though their hosted deployments currently expose health/UI surfaces instead of a stable execution API. Replay mode keeps evaluation deterministic until a direct execution adapter is available.

## AI quality evaluation

Run the five-project replay benchmark:

```bash
PYTHONPATH=. python -m evals.project_runner --target all --mode replay
```

The evaluator persists a batch for each target and stores:

- per-case metric vectors
- target quality score
- gate failures
- replay/live mode
- previous-batch delta
- evaluation notes

The repository intentionally labels replay results as **reference measurements**. They demonstrate the evaluation machinery and metric design; they are not production model benchmarks.

Detailed metric definitions: `docs/AI_EVALUATION.md`.

## Deterministic harness validation

The original harness suites remain useful because they test the **platform mechanics**, not the AI quality itself:

```bash
PYTHONPATH=. python -m evals.runner --workflow all --min-score 90
```

Run the complete test suite:

```bash
PYTHONPATH=. python -m pytest -q
```

## n8n orchestration

Seven importable workflows are included under `workflows/`:

1. AI issue triage + approval
2. AI PR review + approval
3. scheduled experiment digest
4. approval decision webhook
5. LLM health monitor
6. scheduled five-project AI quality regression gate
7. scheduled five-project live fleet health check and audit

See `docs/N8N.md`.

## Observability and governance

Every captured AI call can record:

- workflow / operation
- provider / model
- prompt version
- latency
- success/failure
- fallback use
- input/output/total token counts when available
- estimated cost when pricing is configured
- guardrail state
- error details

The governance layer also persists approvals and audit events. Consequential external actions remain behind human approval in the reference workflows.

## Shared Portfolio LLM Gateway

The harness is provider-agnostic. Projects call the shared Portfolio LLM Gateway rather than hard-coding model-provider credentials into each portfolio repository.

Configure a temporary gateway session token locally:

```env
LLM_PROVIDER=gateway
GATEWAY_BASE_URL=https://portfolio-llm-gateway.onrender.com
GATEWAY_SESSION_TOKEN=<short-lived-gateway-session-token>
GATEWAY_MODEL=<optional>
```

Provider credentials remain on the gateway side. Do not commit provider keys or temporary JWTs.

## Local stack

```bash
cp .env.example .env
docker compose up --build -d
```

Open:

- Dashboard: http://localhost:8000
- API docs: http://localhost:8000/docs
- n8n: http://localhost:5678

The default mode is deterministic/replay-friendly, so the platform runs without an LLM key.

## Target validation

When target URLs are configured, validate the five registered health surfaces with:

```bash
PYTHONPATH=. python scripts/validate_targets.py
```

A target is reported as healthy only when its configured endpoint actually responds. The harness never invents live status.

## Modular extension architecture

The harness is plugin-oriented rather than hard-coded around the five portfolio projects. Four extension points are separated:

```text
Target registration
       ↓
Project adapter
       ↓
Standard AgentRun
       ↓
Evaluation pack
       ↓
Metrics + quality gates
       ↓
Telemetry / regression / audit
       ↓
Dashboard
```

### Project adapters

Each service is wrapped behind the same execution contract:

```python
class AIProjectAdapter:
    async def run(self, workflow: str, payload: dict) -> AgentRun: ...
```

Built-in adapter plugins include `flowpilot`, `legacylens`, `health_only` and `generic_http`. The generic HTTP adapter can integrate a conventional JSON API without writing a custom adapter. More complex services can register a custom adapter for asynchronous tasks, authentication or non-standard response contracts.

### Evaluation packs

Metrics live in reusable workload-specific packs rather than inside individual projects:

- `rag` — Recall@K, Precision@K, MRR, MAP@K, nDCG@K, citations and groundedness
- `agent_workflow` — task/step success, tool validity, policy and approval compliance
- `code_modernization` — syntax, unit tests, semantic verification and release gates
- `document_intelligence` — field accuracy, schema validity, numeric accuracy and risk F1
- `browser_qa` — test generation, defect/regression detection and locator validity

### Versioned datasets

Datasets live separately under `evals/datasets/`. The evaluation runner automatically discovers a registered target when a dataset exists, so a new service does not require changes to the core evaluation runner.

### Configuration-driven external targets

A generic external target can be registered through `EXTRA_TARGETS_JSON` in `.env`. This supplies its adapter, evaluation pack, health endpoint, run endpoint and capabilities without modifying the core API or dashboard. See `docs/EXTENDING.md`.

### Compatibility

The current five projects remain first-class built-in targets. Their adapters and evaluation packs are registered through the same extension contracts used by future external services.

## Production hardening path

SQLite keeps the portfolio version portable. A production multi-instance deployment should use a managed relational database, shared cache/state for circuit breakers, durable object storage for evaluation artifacts, authenticated n8n webhooks, stronger tenancy boundaries and explicit gateway-session refresh.

This repository is a portfolio implementation of these engineering patterns, not a claim of complete enterprise security coverage.

### End-to-end generic integration demo

An optional local `customer-rag` service is included to demonstrate the generic adapter contract end-to-end. It is intentionally isolated in `docker-compose.demo.yml` so the production stack remains unchanged. The demo proves that a sixth external-style service can be registered, health-checked and executed through the same harness API without changing the core evaluation engine.


## Advanced evaluation capabilities

The harness includes experiment comparison, normalized agent trace persistence, prompt/model/config lineage, a replay regression CI gate, and an optional shared-gateway LLM-as-a-judge. These extensions remain decoupled from project adapters and reusable evaluation packs.
