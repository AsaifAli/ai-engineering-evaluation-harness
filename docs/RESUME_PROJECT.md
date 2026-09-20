# Resume-ready project notes

## Project
AI Engineering Automation Hub | n8n, FastAPI, Python, LLMs, GitHub, Docker

## Resume bullet draft — use only after the corresponding features are tested
- Built an AI engineering automation platform using n8n and FastAPI to orchestrate GitHub issue triage, pull-request risk analysis and ML experiment reporting through event-driven workflows.
- Implemented structured AI decision services with human approval gates, audit logging, retry/error paths and API-based integrations to separate LLM reasoning from deterministic workflow execution.
- Containerized the platform with Docker and added CI tests for the AI services and approval lifecycle.

## Interview story
The design intentionally separates the reasoning layer from the automation layer. FastAPI exposes custom AI services, while n8n handles triggers, scheduling, API orchestration, approvals and downstream integrations. This avoids using a workflow automation tool as a substitute for agent state management while still demonstrating practical automation engineering.
