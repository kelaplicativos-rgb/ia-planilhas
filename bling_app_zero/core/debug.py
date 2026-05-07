from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st


def add_debug(message: str, origin: str = 'SISTEMA', level: str = 'INFO') -> None:
    logs = st.session_state.setdefault('logs', [])
    logs.append({
        'hora': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'nivel': str(level or 'INFO'),
        'origem': str(origin or 'SISTEMA'),
        'mensagem': str(message or ''),
    })


def render_debug_panel() -> None:
    logs = st.session_state.get('logs', [])
    with st.sidebar:
        st.markdown('### Debug')
        if not logs:
            st.caption('Nenhum evento registrado ainda.')
            return
        text = '\n'.join(
            f"[{item.get('hora')}] [{item.get('nivel')}] [{item.get('origem')}] {item.get('mensagem')}"
            for item in logs
        )
        st.download_button(
            'Baixar log debug',
            data=text.encode('utf-8'),
            file_name='bling_debug.log',
            mime='text/plain',
            use_container_width=True,
        )
        with st.expander('Ver últimos eventos', expanded=False):
            for item in logs[-20:]:
                st.caption(f"[{item.get('nivel')}] {item.get('origem')}: {item.get('mensagem')}")
