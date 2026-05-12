from __future__ import annotations

from typing import Any

import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/features/state.py'
FEATURE_STATE_PREFIX = 'feature_'
FEATURE_REGISTRY_STATE_KEY = 'features_state_snapshot'


def feature_enabled_key(feature_key: str) -> str:
    return f'{FEATURE_STATE_PREFIX}{feature_key}_enabled'


def feature_config_key(feature_key: str) -> str:
    return f'{FEATURE_STATE_PREFIX}{feature_key}_config'


def is_feature_enabled(feature_key: str, *, default: bool = False) -> bool:
    return bool(st.session_state.get(feature_enabled_key(feature_key), default))


def set_feature_enabled(feature_key: str, enabled: bool) -> None:
    key = feature_enabled_key(feature_key)
    previous = bool(st.session_state.get(key, False))
    current = bool(enabled)
    st.session_state[key] = current
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
        )


def get_feature_config(feature_key: str) -> dict[str, Any]:
    value = st.session_state.get(feature_config_key(feature_key), {})
    return dict(value) if isinstance(value, dict) else {}


def set_feature_config(feature_key: str, config: dict[str, Any]) -> None:
    st.session_state[feature_config_key(feature_key)] = dict(config or {})
    add_audit_event(
        'feature_config_updated',
        area='FEATURES',
        details={
            'feature': feature_key,
            'config_keys': sorted(list((config or {}).keys())),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def clear_feature_state(feature_key: str) -> None:
    removed: list[str] = []
    prefixes = [
        feature_enabled_key(feature_key),
        feature_config_key(feature_key),
        f'{FEATURE_STATE_PREFIX}{feature_key}_',
    ]
    for key in list(st.session_state.keys()):
        text = str(key)
        if any(text == prefix or text.startswith(prefix) for prefix in prefixes):
            removed.append(text)
            st.session_state.pop(key, None)
    add_audit_event(
        'feature_state_cleared',
        area='FEATURES',
        details={'feature': feature_key, 'removed_keys': removed, 'responsible_file': RESPONSIBLE_FILE},
    )


def snapshot_features_state() -> dict[str, Any]:
    snapshot = {
        key: value
        for key, value in st.session_state.items()
        if str(key).startswith(FEATURE_STATE_PREFIX)
    }
    st.session_state[FEATURE_REGISTRY_STATE_KEY] = snapshot
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
