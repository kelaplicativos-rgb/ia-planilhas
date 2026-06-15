from __future__ import annotations

from typing import Final

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.operation_contract import OP_ATUALIZACAO_PRECO, OP_CADASTRO, OP_ESTOQUE, OP_UNIVERSAL, normalize_operation

RESPONSIBLE_FILE: Final[str] = 'bling_app_zero/core/api_operation_lock.py'
CONCRETE_API_OPERATIONS: Final[set[str]] = {OP_CADASTRO, OP_ESTOQUE, OP_ATUALIZACAO_PRECO}

API_CONTEXT_KEYS: Final[tuple[str, ...]] = (
    'home_bling_connected_same_flow_api_send',
    'bling_connected_api_flow_active',
    'direct_bling_api_contract_active',
)
API_OPERATION_KEYS: Final[tuple[str, ...]] = (
    'api_operation',
    'bling_api_operation',
    'home_bling_api_operation_choice',
    'bling_connected_api_operation',
    'direct_bling_operation_choice',
    'direct_bling_operation_applied',
    'flow_spine_sender_operation',
    'flow_spine_operation_resolved_for_api',
    'flow_spine_api_batch_operation',
    'final_download_operation',
    'df_final_download_operation',
    'df_final_preview_operation',
    'home_slim_flow_operation',
    'home_detected_operation',
    'operacao_final',
    'tipo_operacao_final',
    'site_capture_operation',
)


def concrete_api_operation(value: object, *, default: str = '') -> str:
    op = normalize_operation(value, default=OP_UNIVERSAL)
    return op if op in CONCRETE_API_OPERATIONS else default


def api_context_active() -> bool:
    try:
        if any(bool(st.session_state.get(key)) for key in API_CONTEXT_KEYS):
            return True
        finish_mode = str(st.session_state.get('bling_finish_mode') or '').strip().lower()
        if finish_mode in {'api_direct', 'api', 'bling_api'}:
            return True
        destination = str(st.session_state.get('flow_spine_final_destination') or '').strip().lower()
        return destination == 'api_bling'
    except Exception:
        return False


def resolve_api_operation(default: str = '') -> str:
    try:
        for key in API_OPERATION_KEYS:
            op = concrete_api_operation(st.session_state.get(key))
            if op:
                return op
    except Exception:
        return default if default in CONCRETE_API_OPERATIONS else ''
    return default if default in CONCRETE_API_OPERATIONS else ''


def lock_api_operation(operation: object, *, source: str = '', force: bool = False) -> str:
    op = concrete_api_operation(operation)
    if not op:
        return ''
    if not force and not api_context_active():
        return op

    try:
        for key in API_OPERATION_KEYS:
            st.session_state[key] = op
        st.session_state['flow_spine_operation_resolution_source'] = source or RESPONSIBLE_FILE
        st.session_state['api_operation_lock_active'] = True
        st.session_state['api_operation_lock_source'] = source or RESPONSIBLE_FILE
    except Exception:
        return op

    add_audit_event(
        'api_operation_locked_for_api_flow',
        area='BLING_API_FLOW',
        status='OK',
        details={
            'operation': op,
            'source': source or RESPONSIBLE_FILE,
            'force': bool(force),
            'api_context_active': api_context_active(),
            'keys_locked': list(API_OPERATION_KEYS),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return op


__all__ = ['API_OPERATION_KEYS', 'CONCRETE_API_OPERATIONS', 'api_context_active', 'concrete_api_operation', 'lock_api_operation', 'resolve_api_operation']
