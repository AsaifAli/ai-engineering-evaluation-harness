from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .config import GATEWAY_MODEL, HARNESS_CONFIG_VERSION, MODEL_PROMOTION_MIN_SCORE
from .db import (
    ensure_dataset,
    get_model,
    insert_model,
    insert_experiment_run,
    promote_model_record,
    query_datasets,
    query_experiments_runs,
    query_models,
    update_experiment_run,
)

DATASET_ROOT = Path(__file__).resolve().parents[1] / "evals" / "datasets"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _schema_signature(cases: list[Any]) -> str:
    keys: set[str] = set()
    nested: set[str] = set()
    for case in cases:
        if isinstance(case, dict):
            keys.update(str(k) for k in case.keys())
            for key, value in case.items():
                if isinstance(value, dict):
                    nested.update(f"{key}.{nested_key}" for nested_key in value.keys())
    payload = "\n".join(sorted(keys | nested)).encode("utf-8")
    return _sha256_bytes(payload)


def sync_builtin_datasets(version: str = "v1") -> list[dict[str, Any]]:
    """Register deterministic dataset metadata without copying the dataset itself."""
    registered: list[dict[str, Any]] = []
    if not DATASET_ROOT.exists():
        return registered

    for path in sorted(DATASET_ROOT.glob("*.json")):
        raw = path.read_bytes()
        try:
            cases = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(cases, list):
            continue
        registered.append(
            ensure_dataset(
                name=path.stem,
                version=version,
                content_hash=_sha256_bytes(raw),
                schema_hash=_schema_signature(cases),
                sample_count=len(cases),
                metadata={"path": str(path.relative_to(DATASET_ROOT.parent.parent)), "format": "json"},
            )
        )
    return registered


def ensure_runtime_model() -> dict[str, Any]:
    """Register the configured runtime model as an observed candidate."""
    name = GATEWAY_MODEL or "deterministic"
    return insert_model(
        name=name,
        provider="shared-gateway" if GATEWAY_MODEL else "deterministic",
        version="configured",
        status="observed",
        eval_score=None,
        eval_dataset_version=None,
        config_version=HARNESS_CONFIG_VERSION,
        metadata={"runtime_active": True, "managed_by": "agent-harness"},
    )


def create_experiment(
    *,
    name: str,
    target: str,
    model_name: str,
    model_version: str,
    dataset_name: str,
    dataset_version: str,
    prompt_version: str,
    config_version: str,
    parameters: dict[str, Any] | None = None,
) -> str:
    return insert_experiment_run(
        name=name,
        target=target,
        model_name=model_name,
        model_version=model_version,
        dataset_name=dataset_name,
        dataset_version=dataset_version,
        prompt_version=prompt_version,
        config_version=config_version,
        status="running",
        metrics={},
        parameters=parameters or {},
        notes="Created by the evaluation runner.",
    )


def complete_experiment(experiment_id: str, *, metrics: dict[str, Any], status: str, notes: str = "") -> None:
    update_experiment_run(experiment_id, status=status, metrics=metrics, notes=notes)


def promote_model(model_id: str, *, min_score: float | None = None) -> dict[str, Any]:
    threshold = MODEL_PROMOTION_MIN_SCORE if min_score is None else float(min_score)
    model = get_model(model_id)
    if not model:
        raise KeyError("model not found")
    eval_score = model.get("eval_score")
    if eval_score is None:
        raise ValueError("model promotion requires an evaluation score")
    if float(eval_score) < threshold:
        raise ValueError(f"promotion gate failed: eval_score {float(eval_score):.4f} < {threshold:.4f}")
    return promote_model_record(model_id)


def overview() -> dict[str, Any]:
    models = query_models(50)
    datasets = query_datasets(100)
    experiments = query_experiments_runs(50)
    production_models = [m for m in models if m.get("status") == "production"]
    return {
        "model_registry": {"count": len(models), "production": len(production_models), "candidate": sum(m.get("status") == "candidate" for m in models)},
        "dataset_registry": {"count": len(datasets), "active": sum(bool(d.get("active")) for d in datasets)},
        "experiment_tracking": {"count": len(experiments), "completed": sum(e.get("status") == "completed" for e in experiments)},
        "promotion_gate": {"min_eval_score": MODEL_PROMOTION_MIN_SCORE},
        "runtime_model": ensure_runtime_model(),
    }
