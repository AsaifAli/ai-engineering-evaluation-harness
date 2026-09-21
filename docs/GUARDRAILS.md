# Guardrails

The project demonstrates a layered approach:

1. Input size limits.
2. Secret redaction for common API-key/token formats.
3. Prompt-injection signal detection on untrusted GitHub content.
4. Explicit system instructions that GitHub content is data, not instructions.
5. Pydantic validation of model output and enum/range checks.
6. Policy layer that forces manual review when injection signals or low confidence are present.
7. Human approval before external side effects.
8. Audit records for decisions and approvals.

The injection detector is intentionally heuristic. It is a demonstration control, not a complete security solution.
