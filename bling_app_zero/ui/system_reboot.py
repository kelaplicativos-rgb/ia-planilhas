from __future__ import annotations

import time

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.cache_control import clear_streamlit_cache
from bling_app_zero.ui.home_wizard_constants import STEP_MODELO, WIZARD_STEP_KEY

RESPONSIBLE_FILE = 'bling_app_zero/ui/system_reboot.py'
REBOOT_CONFIRM_KEY = 'system_reboot_confirm_visible'
REBOOT_LAST_KEY = 'system_reboot_last_completed_at'

PRESERVE_AFTER_REBOOT_KEYS = {
    REBOOT_LAST_KEY,
}


def _clear_query_params() -> None:
    try:
        st.query_params.clear()
    except Exception:
        try:
            for key in list(st.query_params.keys()):
                del st.query_params[key]
        except Exception:
            pass


def _clear_session_state() -> list[str]:
    removed: list[str] = []
    for key in list(st.session_state.keys()):
        if key in PRESERVE_AFTER_REBOOT_KEYS:
            continue
        removed.append(str(key))
        st.session_state.pop(key, None)
    return removed


def reboot_system_to_home() -> None:
    add_audit_event(
        'system_reboot_requested',
        area='SISTEMA',
        step=st.session_state.get(WIZARD_STEP_KEY),
        status='INICIADO',
        details={'responsible_file': RESPONSIBLE_FILE},
    )

    clear_streamlit_cache(reason='manual_system_reboot')
    removed_keys = _clear_session_state()
    _clear_query_params()

    st.session_state[WIZARD_STEP_KEY] = STEP_MODELO
    st.session_state[REBOOT_LAST_KEY] = time.time()
    st.session_state['system_reboot_completed'] = True

    add_audit_event(
        'system_reboot_completed',
        area='SISTEMA',
        step=STEP_MODELO,
        status='OK',
        details={
            'removed_keys_count': len(removed_keys),
            'removed_keys_sample': removed_keys[:80],
            'home_step': STEP_MODELO,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    st.rerun()


def render_system_reboot_button() -> None:
    if not st.session_state.get(REBOOT_CONFIRM_KEY):
        if st.button('Reiniciar sistema', use_container_width=True, key='system_reboot_open_confirm'):
            st.session_state[REBOOT_CONFIRM_KEY] = True
            add_audit_event(
                'system_reboot_confirm_opened',
                area='SISTEMA',
                step=st.session_state.get(WIZARD_STEP_KEY),
                details={'responsible_file': RESPONSIBLE_FILE},
            )
            st.rerun()
        return

    st.warning(
        'Reiniciar vai limpar arquivos, origem, captura, mapeamentos, precificação, previews, resultados e caches.'
    )
    col_cancel, col_confirm = st.columns(2)
    with col_cancel:
        if st.button('Cancelar', use_container_width=True, key='system_reboot_cancel'):
            st.session_state[REBOOT_CONFIRM_KEY] = False
            add_audit_event(
                'system_reboot_cancelled',
                area='SISTEMA',
                step=st.session_state.get(WIZARD_STEP_KEY),
                details={'responsible_file': RESPONSIBLE_FILE},
            )
            st.rerun()
    with col_confirm:
        if st.button('Sim, limpar tudo', use_container_width=True, key='system_reboot_confirm'):
            reboot_system_to_home()


__all__ = ['reboot_system_to_home', 'render_system_reboot_button']
