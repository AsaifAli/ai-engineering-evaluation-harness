# Security Review — AI Engineering Evaluation Harness

This service is intentionally a public, read-only engineering assurance dashboard plus private telemetry intake. Public read access is a product decision; write routes and operational readiness must be protected.

## Findings and controls
- SQL uses parameter placeholders in `app/db.py`; schema identifiers are regex-validated before interpolation. PASS for observed SQL construction.
- No user-upload or user-supplied HTML surface is present in the API. Dashboard renders a checked-in HTML file; review any future dynamic rendering for escaping.
- The runtime Docker image creates an `appuser` and runs Uvicorn without root privileges; the `/app` data directory remains writable for SQLite.
- CSRF is not applicable to current bearer-header APIs because no cookie-authenticated browser session exists.
- Upload validation is N/A: no upload route.
- SSRF is N/A in the service API; no user-controlled outbound fetch route identified.
- Operator replay writes use `require_hub_api_key` in `app/auth.py`; project event ingestion uses separate project-scoped bearer tokens and constant-time comparison.
- Public telemetry reads currently expose metadata-only event history and evaluation metrics by stated design. Keep the schema allowlisted and do not add source text or PII.
- No local user passwords, MFA flow, JWT issuance, browser session/localStorage token, webhook receiver, or client JS source-map build exists in this application.
- Provider credentials are not used by the service. Operator and per-project tokens are configured server-side.
- Render blueprint keeps ingestion and operator secrets as unsynced deployment environment values.

## Required hardening
1. Application-level IP throttling now covers both write routes; authenticated operator and project ingest credentials have separate quotas (`app/rate_limit.py`, `app/auth.py`). Add shared ingress/WAF quotas for multi-instance deployments because the in-process limiter does not coordinate replicas.
2. **PATCHED in main:** `/ready` returns a generic 503 body and logs only the exception class; database connection details are not reflected to unauthenticated callers.
3. Confirm the dashboard HTML uses safe DOM text APIs and never injects dynamic API values with `innerHTML`.
4. Configure HTTPS-only service access and enable MFA on GitHub/hosting/database administration accounts.
5. Scan the resolved Python dependency environment (including transitive dependencies) and update vulnerable packages after compatibility tests.
6. Confirm database network access is restricted and use a dedicated least-privilege database role. RLS is not applicable to this single-service schema as currently designed; reassess if tenant/user-level data is introduced.

## 20-point checklist
| # | Control | Result |
|---|---|---|
|01|SQLi|PASS — parameterized SQL and validated schema identifier in `app/db.py`|
|02|XSS|PARTIAL — static dashboard; verify dynamic DOM rendering|
|03|CSRF|N/A — bearer header auth, no cookie session|
|04|File upload|N/A — no upload endpoint|
|05|SSRF|N/A — no user-controlled fetch endpoint identified|
|06|BOLA/IDOR|N/A — no user-owned objects; public telemetry is intentional|
|07|Rate limiting|PARTIAL — IP + authenticated operator/project-token quotas are implemented in-process; distributed ingress quotas remain required when scaled|
|08|Password hashing|N/A — no password accounts|
|09|MFA|EXTERNAL — enable for hosting/source-control/database administration|
|10|Server permissions|PASS for writes — operator key and project-scoped ingestion tokens in `app/auth.py`|
|11|RLS|N/A — no multi-tenant user data model; use DB grants/network restrictions|
|12|JWT security|N/A — service does not issue JWTs|
|13|Server-side API keys|PASS — deployment secret variables; no browser provider key|
|14|No localStorage tokens|N/A — no browser-auth session|
|15|No default credentials|PARTIAL — no default operator/ingest secrets in code; provision unique random values|
|16|Strict CORS|N/A for API currently — no browser credentialed CORS policy configured; add explicit allowlist if cross-origin browser calls are added|
|17|Webhook signatures|N/A — no webhook receiver|
|18|Source maps|N/A — no frontend build pipeline|
|19|Clean logs|PARTIAL — no intentional secrets in log format; continue checking exception/log payloads|
|20|Dependency patching|UNVERIFIED — dependency scan required against resolved environment|

## AI audit prompt
Act as a Principal Application Security Engineer. Audit all 20 controls, marking each PASS, PARTIAL, FAIL or N/A with exact file and line references. Do not infer a pass from absence of a search match. Explain exploit risk, create targeted tests for any code patch, and distinguish hosting/network configuration from source-code controls. Never print secret values.