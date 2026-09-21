from __future__ import annotations

from pathlib import Path
from typing import Any

from .command_center import CommandCenterAdapter
from .generic_http import GenericHTTPAdapter
from .health_only import HealthOnlyAdapter
from .legacy_lens import LegacyLensAdapter
from .replay import ReplayAdapter
from ..plugins.registry import adapter_names, create_adapter, register_adapter
from ..targets import TARGETS, TargetSpec, configured_target_url


ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = ROOT / "evals" / "datasets"


# Built-in adapters are registered once at import time. New integrations can add
# a plugin without editing the evaluator or dashboard layers.
for _name, _factory in (
    ("flowpilot", lambda **_: CommandCenterAdapter()),
    ("legacylens", lambda **_: LegacyLensAdapter()),
    ("health_only", lambda *, spec, **_: HealthOnlyAdapter(spec)),
    ("generic_http", lambda *, spec, **_: GenericHTTPAdapter(configured_target_url(spec) or spec.expected_url, run_path=spec.run_path)),
):
    try:
        register_adapter(_name, _factory)
    except ValueError:
        # Safe for test reloads / module re-imports.
        pass


def spec_for(target: str) -> TargetSpec:
    for spec in TARGETS:
        if spec.slug == target:
            return spec
    raise KeyError(f"unknown target: {target}")


def live_adapter(target: str) -> Any:
    spec = spec_for(target)
    return create_adapter(spec.adapter, spec=spec)


def registered_adapter_plugins() -> tuple[str, ...]:
    return adapter_names()


def replay_adapter(target: str) -> ReplayAdapter:
    return ReplayAdapter(target, DATASET_DIR / f"{target}.json")
