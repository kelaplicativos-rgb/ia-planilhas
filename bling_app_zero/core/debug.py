from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st

LOG_SESSION_KEY = 'logs'
MAX_LOG_ITEMS = 300
DEBUG_HOME_OPEN_KEY = 'debug_home_area_open'


def _safe_text(value: Any, limit: int = 4000) -> str:
    text = str(value or '').replace('\x00', '').strip()
    if len(text) > limit:
        return text[:limit] + '...'
    return text


def add_debug(message: str, origin: str = 'SISTEMA', level: str = 'INFO') -> None:
    logs = list(st.session_state.get(LOG_SESSION_KEY, []))
    logs.append(
        {
            'hora': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'nivel': _safe_text(level or 'INFO', 40).upper(),
            'origem': _safe_text(origin or 'SISTEMA', 80),
            'mensagem': _safe_text(message or ''),
        }
    )
    st.session_state[LOG_SESSION_KEY] = logs[-MAX_LOG_ITEMS:]


def _logs_to_text(logs: list[dict[str, Any]]) -> str:
    return '\n'.join(
        f"[{item.get('hora')}] [{item.get('nivel')}] [{item.get('origem')}] {item.get('mensagem')}"
        for item in logs
    )


def _render_debug_actions(logs: list[dict[str, Any]], prefix: str = 'debug') -> None:
    if st.button('Limpar logs', use_container_width=True, key=f'{prefix}_clear_logs'):
        st.session_state[LOG_SESSION_KEY] = []
        st.success('Logs limpos.')
        st.rerun()

    if logs:
        text = _logs_to_text(logs)
        st.download_button(
            'Baixar log debug',
            data=text.encode('utf-8'),
            file_name='bling_debug.log',
            mime='text/plain; charset=utf-8',
            use_container_width=True,
            key=f'{prefix}_download_debug_log_{len(logs)}',
        )


def _render_recent_logs(logs: list[dict[str, Any]], prefix: str = 'debug') -> None:
    show_logs = st.toggle('Ver eventos', value=False, key=f'{prefix}_show_recent_logs')
    if not show_logs:
        return

    with st.container(border=True):
        for item in logs[-25:]:
            level = item.get('nivel', 'INFO')
            origin = item.get('origem', 'SISTEMA')
            message = item.get('mensagem', '')
            st.caption(f'[{level}] {origin}: {message}')


def _render_debug_content(prefix: str = 'debug') -> None:
    logs = list(st.session_state.get(LOG_SESSION_KEY, []))
    _render_debug_actions(logs, prefix=prefix)

    if not logs:
        st.caption('Nenhum evento registrado ainda.')
        return

    st.caption(f'{len(logs)} evento(s) registrado(s).')
    _render_recent_logs(logs, prefix=prefix)


def render_debug_compact_button() -> None:
    if st.button('⚙️', key='open_debug_home_area', help='Logs técnicos'):
        st.session_state[DEBUG_HOME_OPEN_KEY] = not bool(st.session_state.get(DEBUG_HOME_OPEN_KEY, False))


def render_debug_home_area() -> None:
    if not st.session_state.get(DEBUG_HOME_OPEN_KEY, False):
        return

    with st.container(border=True):
        st.markdown('##### Logs técnicos')
        _render_debug_content(prefix='debug_home')


def render_debug_home_button() -> None:
    render_debug_compact_button()
    render_debug_home_area()


def render_debug_panel() -> None:
    with st.sidebar:
        with st.expander('Logs técnicos', expanded=False):
            _render_debug_content(prefix='debug_sidebar')
