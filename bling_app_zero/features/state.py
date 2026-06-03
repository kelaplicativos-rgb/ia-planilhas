from __future__ import annotations

import importlib
from collections.abc import MutableMapping
from typing import Any

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/features/state.py'
FEATURE_STATE_PREFIX = 'feature_'
FEATURE_REGISTRY_STATE_KEY = 'features_state_snapshot'
_FALLBACK_STATE: dict[str, Any] = {}


def _streamlit_module() -> Any | None:
    try:
        return importlib.import_module('streamlit')
    except Exception:
        return None


def _state_store(state: MutableMapping[str, Any] | None = None) -> MutableMapping[str, Any]:
    if state is not None:
        return state
    st = _streamlit_module()
    if st is not None:
        try:
            return st.session_state
        except Exception:
            pass
    return _FALLBACK_STATE


def feature_enabled_key(feature_key: str) -> str:
    return f'{FEATURE_STATE_PREFIX}{feature_key}_enabled'


def feature_config_key(feature_key: str) -> str:
    return f'{FEATURE_STATE_PREFIX}{feature_key}_config'


def is_feature_enabled(feature_key: str, *, default: bool = False, state: MutableMapping[str, Any] | None = None) -> bool:
    store = _state_store(state)
    return bool(store.get(feature_enabled_key(feature_key), default))


def set_feature_enabled(feature_key: str, enabled: bool, *, state: MutableMapping[str, Any] | None = None) -> None:
    store = _state_store(state)
    key = feature_enabled_key(feature_key)
    previous = bool(store.get(key, False))
    current = bool(enabled)
    store[key] = current
    if previous != current:
        add_audit_event(
            'feature_toggle_changed',
            area='FEATURES',
            details={
                'feature': feature_key,
                'previous': previous,
                'enabled': current,
                'state_key': key,
                'responsible_file': RESPONSIBLE_FILE,
            },
            state=store,
        )


def get_feature_config(feature_key: str, *, state: MutableMapping[str, Any] | None = None) -> dict[str, Any]:
    store = _state_store(state)
    value = store.get(feature_config_key(feature_key), {})
    return dict(value) if isinstance(value, dict) else {}


def set_feature_config(feature_key: str, config: dict[str, Any], *, state: MutableMapping[str, Any] | None = None) -> None:
    store = _state_store(state)
    store[feature_config_key(feature_key)] = dict(config or {})
    add_audit_event(
        'feature_config_updated',
        area='FEATURES',
        details={
            'feature': feature_key,
            'config_keys': sorted(list((config or {}).keys())),
            'responsible_file': RESPONSIBLE_FILE,
        },
        state=store,
    )


def clear_feature_state(feature_key: str, *, state: MutableMapping[str, Any] | None = None) -> None:
    store = _state_store(state)
    removed: list[str] = []
    prefixes = [
        feature_enabled_key(feature_key),
        feature_config_key(feature_key),
        f'{FEATURE_STATE_PREFIX}{feature_key}_',
    ]
    for key in list(store.keys()):
        text = str(key)
        if any(text == prefix or text.startswith(prefix) for prefix in prefixes):
            removed.append(text)
            store.pop(key, None)
    add_audit_event(
        'feature_state_cleared',
        area='FEATURES',
        details={'feature': feature_key, 'removed_keys': removed, 'responsible_file': RESPONSIBLE_FILE},
        state=store,
    )


def snapshot_features_state(*, state: MutableMapping[str, Any] | None = None) -> dict[str, Any]:
    store = _state_store(state)
    snapshot = {key: value for key, value in store.items() if str(key).startswith(FEATURE_STATE_PREFIX)}
    store[FEATURE_REGISTRY_STATE_KEY] = snapshot
    return snapshot


__all__ = [
    'FEATURE_REGISTRY_STATE_KEY',
    'FEATURE_STATE_PREFIX',
    'clear_feature_state',
    'feature_config_key',
    'feature_enabled_key',
    'get_feature_config',
    'is_feature_enabled',
    'set_feature_config',
    'set_feature_enabled',
    'snapshot_features_state',
]
