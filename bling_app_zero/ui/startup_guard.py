from __future__ import annotations

import time

import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/startup_guard.py'
BOOT_READY_KEY = 'bling_startup_guard_ready_v1'
BOOT_RENDERED_KEY = 'bling_startup_guard_rendered_once_v1'
BOOT_STARTED_AT_KEY = 'bling_startup_guard_started_at_v1'


def ensure_app_ready() -> bool:
    """Bloqueia a primeira renderização para evitar ações antes do SessionInfo.

    Em celular e Streamlit Cloud, a UI pode aparecer antes de a sessão/websocket
    estabilizar. Botões pesados clicados nesse instante podem gerar:
    "Tried to use SessionInfo before it was initialized".
    """
    if bool(st.session_state.get(BOOT_READY_KEY)):
        return True

    if BOOT_STARTED_AT_KEY not in st.session_state:
        st.session_state[BOOT_STARTED_AT_KEY] = time.time()

    if not bool(st.session_state.get(BOOT_RENDERED_KEY)):
        st.session_state[BOOT_RENDERED_KEY] = True
        add_audit_event(
            'startup_guard_first_render_blocked',
            area='APP',
            status='INFO',
            details={'responsible_file': RESPONSIBLE_FILE},
        )
        st.info('Preparando sessão do sistema...')
        st.progress(20, text='Inicializando conexão segura da tela...')
        time.sleep(0.25)
        st.rerun()
        return False

    st.session_state[BOOT_READY_KEY] = True
    elapsed = round(time.time() - float(st.session_state.get(BOOT_STARTED_AT_KEY) or time.time()), 2)
    add_audit_event(
        'startup_guard_ready',
        area='APP',
        status='OK',
        details={'elapsed_seconds': elapsed, 'responsible_file': RESPONSIBLE_FILE},
    )
    return True


def is_app_ready() -> bool:
    return bool(st.session_state.get(BOOT_READY_KEY))


__all__ = ['ensure_app_ready', 'is_app_ready']
