from __future__ import annotations

import hashlib
import secrets

from fastapi import Header, HTTPException

from .config import HUB_API_KEY
from .rate_limit import RateLimitBackendUnavailable, rate_limiter


def require_hub_api_key(authorization: str | None = Header(default=None)) -> None:
    """Require an operator bearer token for replay-evaluation writes.

    If no operator key is configured, writes are disabled with HTTP 503.
    """
    if not HUB_API_KEY:
        raise HTTPException(status_code=503, detail="operator replay key is not configured")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not token or not secrets.compare_digest(token, HUB_API_KEY):
        raise HTTPException(status_code=401, detail="invalid bearer token")

    from . import config

    fingerprint = hashlib.sha256(token.encode("utf-8")).hexdigest()
    try:
        allowed, retry_after = rate_limiter.check(
            f"hub-token:{fingerprint}",
            limit=config.HUB_RATE_LIMIT_PER_MINUTE,
        )
    except RateLimitBackendUnavailable:
        raise HTTPException(
            status_code=503,
            detail="Write API is temporarily unavailable.",
            headers={"Retry-After": "5"},
        ) from None
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Operator request limit reached. Retry later.",
            headers={"Retry-After": str(retry_after)},
        )


def require_project_ingest_token(project: str, authorization: str | None) -> None:
    """Authenticate a single project's telemetry writer, without admin access."""
    import json

    from . import config

    dedicated_tokens = {
        "evidenceflow": config.HARNESS_EVIDENCEFLOW_INGEST_TOKEN,
        "quotesense": config.HARNESS_QUOTESENSE_INGEST_TOKEN,
        "flowpilot": config.HARNESS_FLOWPILOT_INGEST_TOKEN,
    }
    expected = dedicated_tokens.get(project, "").strip()

    # Dedicated settings let operators rotate one project without rewriting
    # the legacy JSON map, whose existing values may be write-only secrets.
    if not expected:
        try:
            configured = json.loads(config.HARNESS_INGEST_TOKENS_JSON or "{}")
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=503,
                detail="project ingest tokens are misconfigured",
            ) from exc
        expected = configured.get(project) if isinstance(configured, dict) else None
    if not isinstance(expected, str) or not expected.strip():
        raise HTTPException(status_code=503, detail=f"ingest is not configured for {project}")

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing project ingest token")

    supplied = authorization.split(" ", 1)[1].strip()
    if not supplied or not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="invalid project ingest token")

    from . import config

    fingerprint = hashlib.sha256(
        f"{project}:{supplied}".encode("utf-8")
    ).hexdigest()
    try:
        allowed, retry_after = rate_limiter.check(
            f"project-token:{fingerprint}",
            limit=config.PROJECT_INGEST_RATE_LIMIT_PER_MINUTE,
        )
    except RateLimitBackendUnavailable:
        raise HTTPException(
            status_code=503,
            detail="Write API is temporarily unavailable.",
            headers={"Retry-After": "5"},
        ) from None
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Project ingest limit reached. Retry later.",
            headers={"Retry-After": str(retry_after)},
        )
