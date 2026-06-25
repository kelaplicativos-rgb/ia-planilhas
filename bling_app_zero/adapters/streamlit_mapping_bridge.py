from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from bling_app_zero.core.category_mapping_guard import guard_category_mapping
from bling_app_zero.core.critical_empty_fields_guard import strip_critical_empty_mappings
from bling_app_zero.core.mapping_engine import MappingCommandResult, build_mapping_state, build_request_from_frames

RESPONSIBLE_FILE = 'bling_app_zero/adapters/streamlit_mapping_bridge.py'
MAPPING_STATE_KEY = 'neutral_mapping_state_v1'
MAPPING_REPORT_KEY = 'neutral_mapping_report_v1'
CRITICAL_EMPTY_GUARD_KEY = 'neutral_mapping_critical_empty_guard_v1'


def sync_mapping_result(result: MappingCommandResult, *, mapping_state_key: str = '', engine_state_key: str = '') -> None:
    st.session_state[MAPPING_STATE_KEY] = result.state.to_dict()
    st.session_state[MAPPING_REPORT_KEY] = {
        'mapping': result.state.mapping,
        'rows': list(result.rows),
        'engine': result.state.engine,
        'message': result.message,
        'operation': result.state.request.operation,
        'signature': result.state.request.signature,
    }
    if mapping_state_key:
        st.session_state[mapping_state_key] = result.state.mapping
    if engine_state_key:
        st.session_state[engine_state_key] = result.state.engine


def build_and_sync_mapping(source: Any, target: Any, mapping: Mapping[str, str] | None, *, operation: str = 'universal', signature: str = '', engine: str = 'local', mapping_state_key: str = '', engine_state_key: str = '') -> tuple[dict[str, str], list[dict[str, str]]]:
    guarded_mapping, guard_report = guard_category_mapping(source, target, mapping or {})
    guarded_mapping, critical_empty_report = strip_critical_empty_mappings(guarded_mapping)

    request = build_request_from_frames(source, target, operation=operation, signature=signature)
    messages: list[str] = []
    if guard_report:
        messages.append(f'Categorização protegida no mapeamento: {len(guard_report)} ajuste(s).')
        st.session_state['neutral_mapping_category_guard_v1'] = list(guard_report)
    else:
        st.session_state.pop('neutral_mapping_category_guard_v1', None)

    if critical_empty_report:
        messages.append(f'Campos críticos esvaziados no mapeamento: {len(critical_empty_report)} ajuste(s).')
        st.session_state[CRITICAL_EMPTY_GUARD_KEY] = list(critical_empty_report)
    else:
        st.session_state.pop(CRITICAL_EMPTY_GUARD_KEY, None)

    result = build_mapping_state(request, guarded_mapping, source=source, engine=engine, message=' '.join(messages))
    sync_mapping_result(result, mapping_state_key=mapping_state_key, engine_state_key=engine_state_key)
    return result.state.mapping, list(result.rows)


__all__ = ['MAPPING_REPORT_KEY', 'MAPPING_STATE_KEY', 'build_and_sync_mapping', 'sync_mapping_result']
