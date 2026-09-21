from __future__ import annotations

from .packs import PACKS, EvalPack


def get_pack(name: str) -> EvalPack:
    key = str(name).strip().lower()
    try:
        return PACKS[key]
    except KeyError as exc:
        raise KeyError(f"unknown evaluation pack: {name}") from exc


def pack_catalog() -> list[dict[str, object]]:
    return [
        {
            "name": pack.name,
            "description": pack.description,
            "tags": list(pack.tags),
            "gate_count": len(pack.gates),
            "metric_count": len(pack.weights),
        }
        for pack in sorted(PACKS.values(), key=lambda item: item.name)
    ]
