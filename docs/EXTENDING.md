# Extending the Harness

The harness is intentionally modular. The core platform does not contain project-specific execution logic or metric logic. New AI services are added through **adapters**, **evaluation packs**, **datasets**, and **quality-gate configuration**.

## Integration paths

### 1. Generic HTTP service

For a service exposing a JSON run endpoint, register a target with:

```json
[
  {
    "slug": "customer-rag",
    "name": "Customer RAG",
    "role": "External RAG service",
    "repository": "https://example.com/repo",
    "expected_url": "http://host.docker.internal:9001",
    "health_path": "/health",
    "mode": "live_run",
    "adapter": "generic_http",
    "evaluation_pack": "rag",
    "run_path": "/v1/run",
    "configured_env": "CUSTOMER_RAG_BASE_URL",
    "capabilities": ["live_runs", "rag_evaluation"]
  }
]
```

Place the JSON in `EXTRA_TARGETS_JSON` in `.env`. The target is then visible through `/api/integrations` and can use the generic HTTP adapter without editing the core runner.

### 2. Custom execution adapter

Use a custom adapter when the service has asynchronous jobs, authentication, non-standard request/response formats, or domain-specific polling.

```python
class CustomerAdapter(HttpAIProjectAdapter):
    name = "customer-service"

    async def run(self, workflow: str, payload: dict[str, Any]) -> AgentRun:
        ...
```

Register it with the adapter registry and reference the adapter name from the target specification.

### 3. Reusable evaluation pack

Evaluation logic is grouped by workload type in `evals/packs/`:

- `rag` — retrieval, citation and groundedness
- `agent_workflow` — task, tool, policy and approval behavior
- `code_modernization` — syntax, tests and semantic verification
- `document_intelligence` — extraction and structured decision quality
- `browser_qa` — test generation and regression detection

A new pack implements the same `EvalPack` contract:

```python
PACK = EvalPack(
    name="custom_workload",
    evaluator=evaluate,
    gates={"quality_metric": 0.90},
    weights={"quality_metric": 1.0},
    description="...",
    tags=("custom",),
)
```

Then register it in `evals/packs/__init__.py`.

### 4. Versioned dataset

Add `evals/datasets/<target>.json`. Each case contains `expected` and `actual` data for replay evaluation. The runner automatically discovers a registered target when its dataset exists.

Replay data is intentionally labelled as **reference measurement**, not as a production model benchmark.

## Core separation

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
Telemetry / audit / regression
      ↓
Dashboard
```

This separation means a new AI application can be connected without moving evaluation logic into that application or modifying the dashboard implementation.

## Interview-ready integration answer

If an existing service needs this harness, the integration process is:

1. **Choose or implement an adapter** — use `generic_http` for a simple JSON API or a custom adapter for asynchronous jobs/authentication/non-standard contracts.
2. **Register the target** — declare its URL, adapter, workload type, health endpoint and capabilities.
3. **Select or implement an evaluation pack** — reuse `rag`, `agent_workflow`, `code_modernization`, `document_intelligence` or `browser_qa`, or add a new pack.
4. **Add a versioned golden dataset** — expected outputs, relevant evidence, defects, required steps, or other domain-specific references.
5. **Define quality gates** — thresholds appropriate to the service's failure modes.
6. **Run and monitor** — the standardized result flows through evaluation, regression tracking, audit, observability and the existing dashboard.

The application itself does not need to import the harness. The harness integrates at the service boundary.

### 5. Live generic adapter demo

The repository includes an optional local `customer-rag` service to prove the generic adapter contract end-to-end without requiring provider credentials. Start the demo overlay with:

```bash
docker compose -f docker-compose.yml -f docker-compose.demo.yml up --build
```

Then run:

```bash
./scripts/run_generic_target_demo.sh
```

This demonstrates target discovery, health checking, and a real HTTP execution through the harness without modifying the core evaluator.


## Evaluation platform extensions

The platform is intentionally modular across four contracts: adapter, evaluation pack, dataset, and quality gate. Additional LLMOps extensions are also first-class: experiment comparison, trace capture, configuration lineage, CI quality gates, and an optional gateway-backed LLM judge.

### Experiment comparison
Use `POST /api/experiments/compare` with a target and two persisted quality batch IDs. The response reports per-metric baseline/candidate values, directionality, regressions, improvements, score delta, and gate status.

### Agent traces
Adapters may populate `AgentRun.trace` with ordered steps and `AgentRun.metadata` with prompt/model/config versions. The harness persists this in the trace store and exposes it at `GET /api/traces`.

### Configuration lineage
`GET /api/config-registry` exposes registered component versions. Run metadata can carry `prompt_version`, `model_version`, `dataset_version`, and `config_version`.

### LLM-as-a-judge
`POST /api/judge` performs an optional gateway-backed qualitative evaluation. If the shared gateway is not configured, the result is explicitly `skipped`; the harness never fabricates judge scores.

### CI gate
`python -m evals.quality_gate --target all --baseline replay_v1 --max-regression 0.02` runs the deterministic project evaluation suite and fails the process when a project gate fails or its score regresses beyond the configured threshold.
