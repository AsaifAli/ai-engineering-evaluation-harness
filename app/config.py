from __future__ import annotations

import os

DB_PATH = os.getenv("AUDIT_DB", "data/audit.db")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_SCHEMA = os.getenv("DB_SCHEMA", "harness").strip() or "harness"
HARNESS_CONFIG_VERSION = os.getenv("HARNESS_CONFIG_VERSION", "v1")
HUB_API_KEY = os.getenv("HUB_API_KEY", "").strip()
HARNESS_INGEST_TOKENS_JSON = os.getenv("HARNESS_INGEST_TOKENS_JSON", "").strip()

# Process-local backstops for write APIs; configure ingress limits for multi-instance deployments.
HUB_IP_RATE_LIMIT_PER_MINUTE = max(1, int(os.getenv("HUB_IP_RATE_LIMIT_PER_MINUTE", "30")))
HUB_RATE_LIMIT_PER_MINUTE = max(1, int(os.getenv("HUB_RATE_LIMIT_PER_MINUTE", "10")))
PROJECT_INGEST_RATE_LIMIT_PER_MINUTE = max(1, int(os.getenv("PROJECT_INGEST_RATE_LIMIT_PER_MINUTE", "30")))

# Bound write API bodies before JSON/Pydantic parsing (including chunked bodies).
WRITE_REQUEST_MAX_BYTES = max(
    1024,
    int(os.getenv("WRITE_REQUEST_MAX_BYTES", "65536")),
)
