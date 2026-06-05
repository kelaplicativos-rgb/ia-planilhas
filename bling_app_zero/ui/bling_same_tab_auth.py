from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

RESPONSIBLE_FILE = 'bling_app_zero/ui/bling_same_tab_auth.py'


def remember_same_tab_oauth_departure(context: dict[str, Any] | None = None) -> None:
    payload = dict(context or {})
    st.session_state['bling_oauth_same_tab_departure'] = {
        'return_to': str(payload.get('return_to') or 'start'),
        'source_step': str(payload.get('source_step') or 'bling_connection_entry'),
        'message': 'Usuário saiu para autorizar o Bling na mesma aba.',
    }


def render_same_tab_oauth_notice() -> None:
    st.markdown(
        '''
<div style="
    margin:.65rem 0 .75rem 0;
    padding:.78rem .9rem;
    border-radius:.8rem;
    border:1px solid rgba(234,88,12,.32);
    background:rgba(255,237,213,.86);
    color:#7c2d12;
    font-weight:700;
    line-height:1.35;
">
    A autorização do Bling será aberta nesta mesma aba. Depois de autorizar, o sistema volta automaticamente para cá conectado.
</div>
''',
        unsafe_allow_html=True,
    )


def render_same_tab_connect_button(auth_url: str, label: str = 'Conectar ao Bling') -> None:
    safe_url = escape(str(auth_url or '').strip(), quote=True)
    safe_label = escape(str(label or 'Conectar ao Bling'), quote=False)
    if not safe_url:
        st.warning('Não consegui gerar o link de conexão com o Bling agora. Confira Client ID, Client Secret e Redirect URI nos secrets do Streamlit.')
        return
    st.markdown(
        f'''
<a href="{safe_url}" target="_self" rel="nofollow" style="
    display:block;
    width:100%;
    box-sizing:border-box;
    text-align:center;
    text-decoration:none;
    font-weight:900;
    padding:0.86rem 1rem;
    border-radius:0.78rem;
    border:1px solid rgba(37,99,235,.28);
    color:#ffffff;
    background:#2563eb;
    box-shadow:0 10px 22px rgba(37,99,235,.18);
">
    {safe_label}
</a>
''',
        unsafe_allow_html=True,
    )


__all__ = ['remember_same_tab_oauth_departure', 'render_same_tab_connect_button', 'render_same_tab_oauth_notice']
