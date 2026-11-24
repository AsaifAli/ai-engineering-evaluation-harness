from __future__ import annotations

import os

DB_PATH = os.getenv("AUDIT_DB", "data/audit.db")
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_SCHEMA = os.getenv("DB_SCHEMA", "harness").strip() or "harness"
HARNESS_CONFIG_VERSION = os.getenv("HARNESS_CONFIG_VERSION", "v1")
HUB_API_KEY = os.getenv("HUB_API_KEY", "").strip()
HARNESS_INGEST_TOKENS_JSON = os.getenv("HARNESS_INGEST_TOKENS_JSON", "").strip()
