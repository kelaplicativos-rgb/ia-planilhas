from __future__ import annotations

import time

import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/startup_guard.py'
BOOT_READY_KEY = 'bling_startup_guard_ready_v1'
BOOT_RENDERED_KEY = 'bling_startup_guard_rendered_once_v1'
BOOT_STARTED_AT_KEY = 'bling_startup_guard_started_at_v1'


def ensure_app_ready() -> bool:
    """Estabiliza a sessão sem forçar rerun na primeira renderização.

    Em celular e Streamlit Cloud, st.rerun() logo no boot pode provocar o pop-up
    "Bad message format / Tried to use SessionInfo before it was initialized".
    O BLINGFIX mantém a proteção, mas troca o rerun por uma pequena espera local
    e libera a mesma execução. Assim uma operação longa de API não sofre uma
    reinicialização visual desnecessária.
    """
    if bool(st.session_state.get(BOOT_READY_KEY)):
        return True

    if BOOT_STARTED_AT_KEY not in st.session_state:
        st.session_state[BOOT_STARTED_AT_KEY] = time.time()

    if not bool(st.session_state.get(BOOT_RENDERED_KEY)):
        st.session_state[BOOT_RENDERED_KEY] = True
        add_audit_event(
            'startup_guard_first_render_stabilized_without_rerun',
            area='APP',
            status='INFO',
            details={'responsible_file': RESPONSIBLE_FILE},
        )
        notice = st.empty()
        progress = st.progress(20, text='Inicializando conexão segura da tela...')
        notice.info('Preparando sessão do sistema...')
        time.sleep(0.35)
        try:
            progress.progress(100, text='Sessão pronta.')
            time.sleep(0.05)
            progress.empty()
            notice.empty()
        except Exception:
            pass

    st.session_state[BOOT_READY_KEY] = True
    elapsed = round(time.time() - float(st.session_state.get(BOOT_STARTED_AT_KEY) or time.time()), 2)
    add_audit_event(
        'startup_guard_ready',
        area='APP',
        status='OK',
        details={'elapsed_seconds': elapsed, 'no_startup_rerun': True, 'responsible_file': RESPONSIBLE_FILE},
    )
    return True


def is_app_ready() -> bool:
    return bool(st.session_state.get(BOOT_READY_KEY))


__all__ = ['ensure_app_ready', 'is_app_ready']
