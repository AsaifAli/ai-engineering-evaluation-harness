# Observability

The harness records a structured event for every captured AI execution:

- workflow and operation
- provider and model
- prompt version
- wall-clock latency
- success/failure status
- fallback usage
- token usage when exposed by the gateway
- estimated cost when model pricing is configured
- guardrail state
- error detail

For project-level evaluation it also stores:

- target project
- evaluation batch and case id
- replay/live mode
- overall quality score
- metric vector
- gate failures
- evaluation notes

This separation matters: operational telemetry answers **"did the system run reliably?"**, while quality evaluation answers **"did the AI behavior meet task-specific expectations?"**.
