from __future__ import annotations

import secrets

from fastapi import Header, HTTPException

from .config import HUB_API_KEY


def require_hub_api_key(authorization: str | None = Header(default=None)) -> None:
    """Require a bearer token when HUB_API_KEY is configured.

    Local development stays frictionless when the variable is unset. Set HUB_API_KEY on the hosted service to restrict replay-evaluation writes to an operator.
    """
    if not HUB_API_KEY:
        raise HTTPException(status_code=503, detail="operator replay key is not configured")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not token or not secrets.compare_digest(token, HUB_API_KEY):
        raise HTTPException(status_code=401, detail="invalid bearer token")


def require_project_ingest_token(project: str, authorization: str | None) -> None:
    """Authenticate a single project's telemetry writer, without admin access."""
    import json

    from .config import HARNESS_INGEST_TOKENS_JSON

    try:
        configured = json.loads(HARNESS_INGEST_TOKENS_JSON or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=503, detail="project ingest tokens are misconfigured") from exc

    expected = configured.get(project) if isinstance(configured, dict) else None
    if not isinstance(expected, str) or not expected.strip():
        raise HTTPException(status_code=503, detail=f"ingest is not configured for {project}")

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing project ingest token")

    supplied = authorization.split(" ", 1)[1].strip()
    if not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="invalid project ingest token")
