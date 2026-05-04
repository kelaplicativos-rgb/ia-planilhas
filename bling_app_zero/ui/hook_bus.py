from __future__ import annotations

from importlib import import_module
from typing import Any

HOOKS: dict[str, list[str]] = {}


def register(point: str, target: str) -> None:
    items = HOOKS.setdefault(point, [])
    if target not in items:
        items.append(target)


def run(point: str, value: Any = None, **ctx: Any) -> Any:
    current = value
    for target in HOOKS.get(point, []):
        module, name = target.split(":", 1)
        fn = getattr(import_module(module), name)
        current = fn(current, **ctx)
    return current
