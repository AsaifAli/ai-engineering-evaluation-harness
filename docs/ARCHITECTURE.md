# Architecture and interview story

## Control-plane responsibilities

**n8n:** event triggers, schedules, sequencing, external integrations and approval routing.

**FastAPI:** domain logic, guardrails, structured output validation, deterministic comparison logic, reliability controls, telemetry and audit APIs.

**Shared Portfolio LLM Gateway:** provider/BYOK abstraction and model routing. The Hub only receives a temporary session token.

**Evaluation runner:** versioned golden cases and regression scoring for the five portfolio AI workloads, with reusable evaluation packs.

**Dashboard:** operational observability and review surface; it is not another workflow engine.

## Why the LLM does not own numerical experiment comparison

Metric comparison is deterministic. This prevents a language model from inventing or changing the regression result. The LLM only explains already-computed findings.

## Human-in-the-loop boundary

AI output is decision support. External side effects such as labels, comments or notifications happen only after approval through the n8n workflow.

## Cross-project adapter layer

The harness is a middle infrastructure layer across the five portfolio AI systems:

1. FlowPilot — AI Automation Command Center
2. LegacyLens — Agentic Software Modernization
3. EvidenceFlow — Verified Sparse-First RAG
4. QuoteSense — Procurement Intelligence
5. WebQA Intelligence — AI-Assisted Testing

Each target is registered behind an adapter contract. Live-capable targets use project-specific execution APIs; targets that currently expose only a hosted UI or health surface are registered in health/replay mode until a stable execution API is available.

## Target validation

Use `python scripts/validate_targets.py` to validate the five registered target surfaces. A target is marked `healthy` only when its configured health endpoint responds successfully. The harness does not invent live status for targets whose services are unavailable, expired, or unconfigured.

## Modular integration model

The platform separates four contracts so external AI services can be integrated without changing the core dashboard or orchestration layer:

- **Target registration** — URL, health surface, capabilities, adapter and workload/evaluation pack.
- **Project adapter** — translates service-specific execution and telemetry into the standard `AgentRun` contract.
- **Evaluation pack** — reusable metrics, weights and quality gates for a workload type such as RAG or agentic workflows.
- **Versioned dataset** — target-specific golden cases used for replay and regression evaluation.

A simple JSON API can use the built-in `generic_http` adapter. Complex services can provide a custom adapter plugin. Evaluation packs are reusable across services, so a new RAG system can use the same retrieval/grounding benchmark design as EvidenceFlow.
