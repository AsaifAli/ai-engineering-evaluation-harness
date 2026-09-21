from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

Evaluator = Callable[[dict[str, Any], dict[str, Any]], dict[str, float]]


@dataclass(frozen=True)
class EvalPack:
    name: str
    evaluator: Evaluator
    gates: dict[str, float]
    weights: dict[str, float]
    description: str
    tags: tuple[str, ...] = ()
