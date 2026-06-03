from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

RESPONSIBLE_FILE = 'bling_app_zero/core/app_state.py'


@dataclass
class AppState:
    values: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.values[key] = value

    def pop(self, key: str, default: Any = None) -> Any:
        return self.values.pop(key, default)

    def has(self, key: str) -> bool:
        return key in self.values

    def update(self, values: Mapping[str, Any]) -> None:
        for key, value in values.items():
            self.values[str(key)] = value

    def clear(self) -> None:
        self.values.clear()

    def keys(self) -> list[str]:
        return list(self.values.keys())

    def snapshot(self) -> dict[str, Any]:
        return dict(self.values)

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any] | None = None) -> 'AppState':
        return cls(dict(values or {}))


def copy_selected_state(source: Mapping[str, Any], *, prefixes: tuple[str, ...] = (), keys: tuple[str, ...] = ()) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in source.items():
        text = str(key)
        if text in keys or any(text.startswith(prefix) for prefix in prefixes):
            out[text] = value
    return out


def clear_by_keys_and_prefixes(state: AppState, *, keys: tuple[str, ...] = (), prefixes: tuple[str, ...] = ()) -> None:
    for key in keys:
        state.pop(key, None)
    for key in list(state.keys()):
        if any(str(key).startswith(prefix) for prefix in prefixes):
            state.pop(str(key), None)


__all__ = ['AppState', 'clear_by_keys_and_prefixes', 'copy_selected_state']
