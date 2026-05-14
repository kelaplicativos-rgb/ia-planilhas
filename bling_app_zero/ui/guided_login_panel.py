from __future__ import annotations

import streamlit as st

RESPONSIBLE_FILE = 'bling_app_zero/ui/guided_login_panel.py'
LEGACY_KEYS = (
    'guided_login_confirmed_logged_in',
    'guided_login_capture_config',
    'guided_login_capture_prompt',
    'guided_login_capture_last_prepared_at',
    'guided_login_security_resolved',
    'guided_login_products_page_ready',
    'guided_login_capture_mode',
    'guided_login_remote_snapshot_url',
    'guided_login_remote_snapshot_final_url',
    'guided_login_remote_snapshot_title',
    'guided_login_remote_snapshot_ok',
    'guided_login_remote_snapshot_png',
    'guided_login_remote_last_click_nonce',
    'guided_login_remote_desktop_ready',
    'guided_login_remote_desktop_url_ready',
)


def _orange_warning(message: str) -> None:
    st.markdown(
        f'<div style="background:#fff3e0;border:1px solid #ffcc80;border-left:6px solid #fb8c00;color:#5d3200;border-radius:12px;padding:12px 14px;margin:8px 0;font-size:0.95rem;">⚠️ {message}</div>',
        unsafe_allow_html=True,
    )


def _disable_legacy_authenticated_capture() -> None:
    for key in LEGACY_KEYS:
        st.session_state.pop(key, None)
    for key in list(st.session_state.keys()):
        if str(key).startswith('site_guided_login_enabled_'):
            st.session_state[key] = False


def render_guided_login_panel() -> None:
    """Compatibilidade temporária para import antigo do site_panel.

    O fluxo de fornecedor autenticado/navegador remoto foi removido do produto.
    Este painel existe apenas para evitar ModuleNotFoundError enquanto o site_panel.py
    legado ainda é substituído pela versão limpa.
    """
    _disable_legacy_authenticated_capture()
    st.markdown('##### Captura autenticada removida')
    _orange_warning(
        'O fluxo antigo de fornecedor autenticado foi desativado. Use a busca normal por links públicos ou a compatibilidade universal para importar HTML/CSV/XLSX/tabela copiada do fornecedor.'
    )
    st.caption(f'Arquivo de compatibilidade: {RESPONSIBLE_FILE}')


__all__ = ['render_guided_login_panel']
