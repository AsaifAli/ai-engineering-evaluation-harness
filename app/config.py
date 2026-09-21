from __future__ import annotations

import os

DB_PATH = os.getenv("AUDIT_DB", "data/audit.db")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "deterministic").strip().lower()
GATEWAY_BASE_URL = os.getenv("GATEWAY_BASE_URL", "https://portfolio-llm-gateway.onrender.com").rstrip("/")
GATEWAY_SESSION_TOKEN = os.getenv("GATEWAY_SESSION_TOKEN", "").strip()
GATEWAY_MODEL = os.getenv("GATEWAY_MODEL", "").strip()
GATEWAY_PROVIDER = os.getenv("GATEWAY_PROVIDER", "gateway").strip()
GATEWAY_TIMEOUT = float(os.getenv("GATEWAY_TIMEOUT", "45"))
GATEWAY_MAX_RETRIES = int(os.getenv("GATEWAY_MAX_RETRIES", "2"))
CIRCUIT_FAILURE_THRESHOLD = int(os.getenv("CIRCUIT_FAILURE_THRESHOLD", "3"))
CIRCUIT_RECOVERY_SECONDS = float(os.getenv("CIRCUIT_RECOVERY_SECONDS", "30"))
MAX_INPUT_CHARS = int(os.getenv("MAX_INPUT_CHARS", "12000"))
MIN_CONFIDENCE_FOR_ACTION = float(os.getenv("MIN_CONFIDENCE_FOR_ACTION", "0.70"))
MODEL_PRICING_JSON = os.getenv("MODEL_PRICING_JSON", "{}")
HARNESS_CONFIG_VERSION = os.getenv("HARNESS_CONFIG_VERSION", "v1")

COMMAND_CENTER_BASE_URL = os.getenv("COMMAND_CENTER_BASE_URL", "http://host.docker.internal:8000").rstrip("/")
COMMAND_CENTER_API_KEY = os.getenv("COMMAND_CENTER_API_KEY", "")
COMMAND_CENTER_LLM_GATEWAY_TOKEN = os.getenv("COMMAND_CENTER_LLM_GATEWAY_TOKEN", "")
COMMAND_CENTER_TIMEOUT = float(os.getenv("COMMAND_CENTER_TIMEOUT", "90"))

LEGACY_LENS_BASE_URL = os.getenv("LEGACY_LENS_BASE_URL", "").strip().rstrip("/")
LEGACY_LENS_AUTHORIZATION = os.getenv("LEGACY_LENS_AUTHORIZATION", "").strip()
LEGACY_LENS_GATEWAY_TOKEN = os.getenv("LEGACY_LENS_GATEWAY_TOKEN", "").strip()
LEGACY_LENS_TIMEOUT = float(os.getenv("LEGACY_LENS_TIMEOUT", "120"))
EVIDENCEFLOW_BASE_URL = os.getenv("EVIDENCEFLOW_BASE_URL", "").strip().rstrip("/")
QUOTESENSE_BASE_URL = os.getenv("QUOTESENSE_BASE_URL", "").strip().rstrip("/")
WEBQA_BASE_URL = os.getenv("WEBQA_BASE_URL", "").strip().rstrip("/")

EXTRA_TARGETS_JSON = os.getenv("EXTRA_TARGETS_JSON", "").strip()
