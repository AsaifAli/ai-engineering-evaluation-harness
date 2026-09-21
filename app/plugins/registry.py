from __future__ import annotations

from typing import Any

from .contracts import ProjectAdapterPlugin


_ADAPTERS: dict[str, Any] = {}


def register_adapter(name: str, factory: Any) -> None:
    """Register an adapter factory under a stable plugin name."""
    key = str(name).strip().lower()
    if not key:
        raise ValueError("adapter name cannot be empty")
    if key in _ADAPTERS:
        raise ValueError(f"adapter already registered: {key}")
    _ADAPTERS[key] = factory


def adapter_names() -> tuple[str, ...]:
    return tuple(sorted(_ADAPTERS))


def create_adapter(name: str, **kwargs: Any) -> ProjectAdapterPlugin:
    try:
        factory = _ADAPTERS[str(name).strip().lower()]
    except KeyError as exc:
        raise KeyError(f"unknown adapter plugin: {name}") from exc
    return factory(**kwargs)
