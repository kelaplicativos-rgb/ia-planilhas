from __future__ import annotations

from importlib import import_module
from typing import Any


def call(module: str, name: str, *args: Any, **kwargs: Any) -> Any:
    fn = getattr(import_module(module), name)
    return fn(*args, **kwargs)
