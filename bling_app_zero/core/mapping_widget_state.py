from __future__ import annotations

import importlib
from collections.abc import MutableMapping
from typing import Any

AUDIT_STATE_SNAPSHOT_KEY = 'audit_state_snapshot'
MAPPING_WIDGET_MARKERS = ('cad_map_', 'stk_map_')
MAPPING_VALUE_SUFFIXES = (
    '__manual_value',
    '__manual_resolved',
    '__empty_resolved',
)
_FALLBACK_STATE: dict[str, Any] = {}


def _streamlit_module() -> Any | None:
    try:
        return importlib.import_module('streamlit')
    except Exception:
        return None


def state_store(state: MutableMapping[str, Any] | None = None) -> MutableMapping[str, Any]:
    if state is not None:
        return state
    st = _streamlit_module()
    if st is not None:
        try:
            return st.session_state
        except Exception:
            pass
    return _FALLBACK_STATE


def _is_mapping_widget_state_key(key: Any) -> bool:
    text = str(key or '')
    return text.startswith(MAPPING_WIDGET_MARKERS) and text.endswith(MAPPING_VALUE_SUFFIXES)


def _value_from_snapshot_item(item: Any) -> Any:
    if not isinstance(item, dict):
        return None
    return item.get('value')


def restore_mapping_widget_state_from_snapshot(state: MutableMapping[str, Any] | None = None) -> None:
    """Restaura valores manuais de mapeamento que saem da tela por paginação."""
    store = state_store(state)
    snapshot = store.get(AUDIT_STATE_SNAPSHOT_KEY)
    if not isinstance(snapshot, dict):
        return

    restored: list[str] = []
    for key, item in snapshot.items():
        if not _is_mapping_widget_state_key(key):
            continue
        if key in store:
            continue
        value = _value_from_snapshot_item(item)
        if value is None:
            continue
        store[key] = value
        restored.append(str(key))

    if restored:
        store['mapping_widget_state_restored_keys'] = restored[-80:]


__all__ = ['restore_mapping_widget_state_from_snapshot', 'state_store']
