from __future__ import annotations

from typing import Any

import streamlit as st

AUDIT_STATE_SNAPSHOT_KEY = 'audit_state_snapshot'
MAPPING_WIDGET_MARKERS = ('cad_map_', 'stk_map_')
MAPPING_VALUE_SUFFIXES = (
    '__manual_value',
    '__manual_resolved',
    '__empty_resolved',
)


def _is_mapping_widget_state_key(key: Any) -> bool:
    text = str(key or '')
    return text.startswith(MAPPING_WIDGET_MARKERS) and text.endswith(MAPPING_VALUE_SUFFIXES)


def _value_from_snapshot_item(item: Any) -> Any:
    if not isinstance(item, dict):
        return None
    return item.get('value')


def restore_mapping_widget_state_from_snapshot() -> None:
    """Restaura valores manuais de mapeamento que saem da tela por paginação.

    O Streamlit remove do session_state os widgets que deixam de ser renderizados.
    No mapeamento em blocos, isso pode apagar valores de "escrever valor fixo"
    quando o usuário navega para outro bloco. Esta proteção restaura apenas chaves
    internas de mapeamento manual a partir do último snapshot do audit trail.
    """
    snapshot = st.session_state.get(AUDIT_STATE_SNAPSHOT_KEY)
    if not isinstance(snapshot, dict):
        return

    restored: list[str] = []
    for key, item in snapshot.items():
        if not _is_mapping_widget_state_key(key):
            continue
        if key in st.session_state:
            continue
        value = _value_from_snapshot_item(item)
        if value is None:
            continue
        st.session_state[key] = value
        restored.append(str(key))

    if restored:
        st.session_state['mapping_widget_state_restored_keys'] = restored[-80:]


__all__ = ['restore_mapping_widget_state_from_snapshot']
