from __future__ import annotations

import secrets

from fastapi import Header, HTTPException

from .config import HUB_API_KEY


def require_hub_api_key(authorization: str | None = Header(default=None)) -> None:
    """Require a bearer token when HUB_API_KEY is configured.

    Local development stays frictionless when the variable is unset. Render should
    set HUB_API_KEY so n8n and other automation clients authenticate explicitly.
    """
    if not HUB_API_KEY:
        return
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not token or not secrets.compare_digest(token, HUB_API_KEY):
        raise HTTPException(status_code=401, detail="invalid bearer token")
