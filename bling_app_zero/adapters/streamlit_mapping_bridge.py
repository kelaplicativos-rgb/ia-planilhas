from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from bling_app_zero.core.mapping_engine import MappingCommandResult, build_mapping_state, build_request_from_frames

RESPONSIBLE_FILE = 'bling_app_zero/adapters/streamlit_mapping_bridge.py'
MAPPING_STATE_KEY = 'neutral_mapping_state_v1'
MAPPING_REPORT_KEY = 'neutral_mapping_report_v1'


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
    # BLINGFIX: o sync do mapeamento não pode bloquear nenhuma coluna.
    # Categoria, Tags, Código Pai e qualquer outro campo devem seguir a decisão do usuário:
    # vazio fica vazio; coluna selecionada é usada; valor fixo é preservado.
    user_mapping = {str(key): str(value or '').strip() for key, value in dict(mapping or {}).items()}
    st.session_state.pop('neutral_mapping_category_guard_v1', None)
    st.session_state.pop('neutral_mapping_critical_empty_guard_v1', None)
    request = build_request_from_frames(source, target, operation=operation, signature=signature)
    result = build_mapping_state(request, user_mapping, source=source, engine=engine, message='Mapeamento salvo respeitando a escolha do usuário.')
    sync_mapping_result(result, mapping_state_key=mapping_state_key, engine_state_key=engine_state_key)
    return result.state.mapping, list(result.rows)


__all__ = ['MAPPING_REPORT_KEY', 'MAPPING_STATE_KEY', 'build_and_sync_mapping', 'sync_mapping_result']
