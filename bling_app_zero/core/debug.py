from __future__ import annotations

from datetime import datetime
from typing import Any

import streamlit as st

from bling_app_zero.core.user_rules import RULE_OPTIONS, default_rules, get_user_rules

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
    add_debug('Cache do Streamlit limpo.', origin='DEBUG', level='INFO')


def _render_debug_actions(logs: list[dict[str, Any]], prefix: str = 'debug') -> None:
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button('Limpar logs', use_container_width=True, key=f'{prefix}_clear_logs'):
            st.session_state[LOG_SESSION_KEY] = []
            st.success('Logs limpos.')
            st.rerun()
    with col_b:
        if st.button('Limpar cache', use_container_width=True, key=f'{prefix}_clear_cache'):
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


def _render_rules_snapshot(prefix: str = 'debug') -> None:
    rules = get_user_rules()
    show_rules = st.toggle('Regras e padrões atuais', value=False, key=f'{prefix}_show_rules_snapshot')
    if not show_rules:
        return

    with st.container(border=True):
        for option in RULE_OPTIONS:
            value = rules.get(option.key, default_rules().get(option.key, ''))
            label = option.label.replace(' padrão', '')
            st.caption(f'{label}: {value}')
        st.caption(f'Regras personalizadas: {len(rules.get("custom_rules", []))}')
        st.caption('Para editar esses padrões, use o painel lateral “Padrões do CSV final”.')


def _render_debug_content(prefix: str = 'debug') -> None:
    logs = list(st.session_state.get(LOG_SESSION_KEY, []))
    _render_debug_actions(logs, prefix=prefix)
    _render_rules_snapshot(prefix=prefix)

    if not logs:
        st.caption('Nenhum evento registrado ainda.')
        return

    st.caption(f'{len(logs)} evento(s) registrado(s).')
    _render_recent_logs(logs, prefix=prefix)


def render_debug_home_button() -> None:
    """Atalho discreto da área técnica próximo ao card do topo."""
    st.markdown(
        """
        <style>
        div[data-testid="stVerticalBlock"]:has(#bling-tech-anchor) {
            margin-top: -3.20rem !important;
            margin-bottom: 1.15rem !important;
            pointer-events: none;
        }
        div[data-testid="stVerticalBlock"]:has(#bling-tech-anchor) .stButton {
            display: flex !important;
            justify-content: flex-end !important;
            padding-right: 1.55rem !important;
            pointer-events: auto;
        }
        div[data-testid="stVerticalBlock"]:has(#bling-tech-anchor) .stButton > button {
            min-height: 32px !important;
            height: 32px !important;
            width: 32px !important;
            border-radius: 999px !important;
            padding: 0 !important;
            font-size: 0.90rem !important;
            opacity: 0.70;
            border: 1px solid rgba(15,23,42,0.14) !important;
            background: rgba(255,255,255,0.88) !important;
            box-shadow: 0 6px 14px rgba(15,23,42,0.08) !important;
        }
        div[data-testid="stVerticalBlock"]:has(#bling-tech-anchor) .stButton > button:hover {
            opacity: 1;
            border-color: rgba(185,28,28,0.32) !important;
        }
        @media (max-width: 760px) {
            div[data-testid="stVerticalBlock"]:has(#bling-tech-anchor) {
                margin-top: -3.05rem !important;
                margin-bottom: 1.0rem !important;
            }
            div[data-testid="stVerticalBlock"]:has(#bling-tech-anchor) .stButton {
                padding-right: 1.05rem !important;
            }
        }
        </style>
        <span id="bling-tech-anchor"></span>
        """,
        unsafe_allow_html=True,
    )

    if st.button('⚙️', key='open_debug_home_area', help='Área técnica'):
        st.session_state[DEBUG_HOME_OPEN_KEY] = not bool(st.session_state.get(DEBUG_HOME_OPEN_KEY, False))

    if not st.session_state.get(DEBUG_HOME_OPEN_KEY, False):
        return

    with st.container(border=True):
        st.markdown('##### Área técnica')
        _render_debug_content(prefix='debug_home')


def render_debug_panel() -> None:
    with st.sidebar:
        with st.expander('Suporte, logs e regras', expanded=False):
            _render_debug_content(prefix='debug_sidebar')
