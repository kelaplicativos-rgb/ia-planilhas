from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.operation_safety_guard import install_preventive_operation_guard

RESPONSIBLE_FILE = 'bling_app_zero/ui/preventive_bootstrap.py'
MOBILE_CONNECTED_AUTO_ENTRY_KEY = 'mobile_connected_bling_auto_entry_done_v1'
EXPLICIT_API_SEND_KEY = 'home_bling_connected_same_flow_api_send'
FINISH_MODE_KEY = 'bling_finish_mode'
API_SESSION_KEYS = (
    'bling_connected_api_flow_active',
    'bling_connected_api_operation',
    'bling_connected_origin_kind',
    'bling_connected_next_human_step',
    'df_final_bling_api',
    'mapping_bling_api',
    'mapping_confidence_bling_api',
    'bling_api_automation_mapping_skipped',
    'bling_api_automation_rows',
    'bling_api_automation_columns',
    'bling_api_required_selector',
    'bling_api_must_run_ai_check',
    'bling_api_final_action',
)


def _disable_connection_driven_auto_entry() -> None:
    """A conexão libera a API, mas nunca escolhe um fluxo pelo usuário."""
    was_enabled = bool(st.session_state.get(MOBILE_CONNECTED_AUTO_ENTRY_KEY))
    st.session_state[MOBILE_CONNECTED_AUTO_ENTRY_KEY] = True
    if not was_enabled:
        add_audit_event(
            'connection_driven_auto_entry_disabled',
            area='HOME',
            step='startup',
            status='OK',
            details={
                'connection_only': True,
                'requires_explicit_home_selection': True,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )


def _clear_inactive_api_session() -> None:
    explicit_api = bool(st.session_state.get(EXPLICIT_API_SEND_KEY))
    finish_mode = str(st.session_state.get(FINISH_MODE_KEY) or '').strip().lower()
    if explicit_api or finish_mode == 'api_direct':
        return

    removed: list[str] = []
    for key in API_SESSION_KEYS:
        if key in st.session_state:
            st.session_state.pop(key, None)
            removed.append(key)
    if removed:
        add_audit_event(
            'inactive_api_session_cleared_for_manual_flow',
            area='HOME',
            step='startup',
            status='OK',
            details={
                'removed_keys': removed,
                'manual_mapping_preserved': True,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )


def install_preventive_bootstrap() -> None:
    """Executa proteções leves no boot sem derrubar a UI.

    Este bootstrap é intencionalmente defensivo: qualquer falha nele vira log de
    aviso e o app principal continua abrindo. Ele existe para evitar que uma
    operação presa deixe o usuário sem saída entre reruns do Streamlit.
    """
    _disable_connection_driven_auto_entry()
    _clear_inactive_api_session()
    try:
        decision = install_preventive_operation_guard(st.session_state)
        if not decision.ok:
            st.warning(decision.message)
            add_audit_event(
                'preventive_bootstrap_user_notice_rendered',
                area='APP',
                step='startup',
                status='AVISO',
                details={
                    'reason': decision.reason,
                    'details': decision.details or {},
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
    except Exception as exc:
        add_audit_event(
            'preventive_bootstrap_failed_non_blocking',
            area='APP',
            step='startup',
            status='AVISO',
            details={'error': str(exc)[:300], 'responsible_file': RESPONSIBLE_FILE},
        )


__all__ = ['install_preventive_bootstrap']
