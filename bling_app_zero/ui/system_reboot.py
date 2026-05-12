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
    """Limpa cache, session_state e query params, voltando ao início do Wizard."""
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
    """Botão inferior global: reinicia o fluxo inteiro com confirmação visual."""
    st.markdown(
        """
        <style>
        .bling-reboot-box {
            margin-top: 1.15rem;
            padding: .95rem 1rem;
            border-radius: 18px;
            background: #fff7ed;
            border: 1px solid #fed7aa;
            box-shadow: 0 10px 24px rgba(146, 64, 14, .07);
        }
        .bling-reboot-title {
            color: #9a3412;
            font-weight: 900;
            font-size: .94rem;
            margin-bottom: .18rem;
        }
        .bling-reboot-text {
            color: #7c2d12;
            font-weight: 650;
            font-size: .88rem;
            line-height: 1.35;
            margin: 0;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if not st.session_state.get(REBOOT_CONFIRM_KEY):
        if st.button('🔄 Reiniciar sistema e voltar para Home', use_container_width=True, key='system_reboot_open_confirm'):
            st.session_state[REBOOT_CONFIRM_KEY] = True
            add_audit_event(
                'system_reboot_confirm_opened',
                area='SISTEMA',
                step=st.session_state.get(WIZARD_STEP_KEY),
                details={'responsible_file': RESPONSIBLE_FILE},
            )
            st.rerun()
        return

    st.markdown(
        """
        <div class="bling-reboot-box" role="alert">
            <div class="bling-reboot-title">⚠️ Reiniciar sistema inteiro?</div>
            <p class="bling-reboot-text">
                Isso vai limpar arquivos carregados, origem, captura por site, mapeamentos, precificação,
                previews, resultados finais, caches e voltar para a Home como se o app tivesse acabado de abrir.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col_cancel, col_confirm = st.columns(2)
    with col_cancel:
        if st.button('Cancelar reinício', use_container_width=True, key='system_reboot_cancel'):
            st.session_state[REBOOT_CONFIRM_KEY] = False
            add_audit_event(
                'system_reboot_cancelled',
                area='SISTEMA',
                step=st.session_state.get(WIZARD_STEP_KEY),
                details={'responsible_file': RESPONSIBLE_FILE},
            )
            st.rerun()
    with col_confirm:
        if st.button('✅ Sim, limpar tudo e voltar para Home', use_container_width=True, key='system_reboot_confirm'):
            reboot_system_to_home()


__all__ = ['reboot_system_to_home', 'render_system_reboot_button']
