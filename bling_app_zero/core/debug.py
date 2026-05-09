from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st

LOG_SESSION_KEY = 'logs'
MAX_LOG_ITEMS = 300


def _safe_text(value: Any, limit: int = 4000) -> str:
    text = str(value or '').replace('\x00', '').strip()
    if len(text) > limit:
        return text[:limit] + '...'
    return text


def add_debug(message: str, origin: str = 'SISTEMA', level: str = 'INFO') -> None:
    logs = list(st.session_state.get(LOG_SESSION_KEY, []))
    logs.append({
        'hora': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'nivel': _safe_text(level or 'INFO', 40).upper(),
        'origem': _safe_text(origin or 'SISTEMA', 80),
        'mensagem': _safe_text(message or ''),
    })
    st.session_state[LOG_SESSION_KEY] = logs[-MAX_LOG_ITEMS:]


def _logs_to_text(logs: list[dict[str, Any]]) -> str:
    return '\n'.join(
        f"[{item.get('hora')}] [{item.get('nivel')}] [{item.get('origem')}] {item.get('mensagem')}"
        for item in logs
    )


def _clear_app_cache() -> None:
    try:
        st.cache_data.clear()
    except Exception:
        pass
    try:
        st.cache_resource.clear()
    except Exception:
        pass
    add_debug('Cache do Streamlit limpo pelo painel lateral.', origin='DEBUG', level='INFO')


def _render_debug_actions(logs: list[dict[str, Any]]) -> None:
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button('Limpar logs', use_container_width=True, key='debug_clear_logs'):
            st.session_state[LOG_SESSION_KEY] = []
            st.success('Logs limpos.')
            st.rerun()
    with col_b:
        if st.button('Limpar cache', use_container_width=True, key='debug_clear_cache'):
            _clear_app_cache()
            st.success('Cache limpo.')
            st.rerun()

    if logs:
        text = _logs_to_text(logs)
        st.download_button(
            'Baixar log debug',
            data=text.encode('utf-8'),
            file_name='bling_debug.log',
            mime='text/plain; charset=utf-8',
            use_container_width=True,
            key=f'download_debug_log_{len(logs)}',
        )


def render_debug_panel() -> None:
    logs = list(st.session_state.get(LOG_SESSION_KEY, []))
    with st.sidebar:
        with st.expander('Suporte e logs', expanded=False):
            st.caption('Use esta área apenas para conferir erros, baixar logs ou limpar cache durante testes.')
            _render_debug_actions(logs)

            if not logs:
                st.caption('Nenhum evento registrado ainda.')
                return

            st.caption(f'{len(logs)} evento(s) registrado(s).')
            with st.expander('Ver últimos eventos', expanded=False):
                for item in logs[-25:]:
                    level = item.get('nivel', 'INFO')
                    origin = item.get('origem', 'SISTEMA')
                    message = item.get('mensagem', '')
                    st.caption(f'[{level}] {origin}: {message}')
