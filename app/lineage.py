from __future__ import annotations

from typing import Any

from .config import HARNESS_CONFIG_VERSION


def default_lineage(*, dataset_version: str = "v1", prompt_version: str = "not-applicable", model_version: str = "not-applicable", config_version: str | None = None) -> dict[str, str]:
    return {
        "dataset_version": dataset_version,
        "prompt_version": prompt_version,
        "model_version": model_version,
        "config_version": config_version or HARNESS_CONFIG_VERSION,
    }


def merge_lineage(base: dict[str, Any], override: dict[str, Any] | None) -> dict[str, Any]:
    result = dict(base)
    if override:
        for key in ("dataset_version", "prompt_version", "model_version", "config_version"):
            value = override.get(key)
            if value not in (None, ""):
                result[key] = str(value)
    return result
