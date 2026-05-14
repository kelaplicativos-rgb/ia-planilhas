from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

LOG_SESSION_KEY = 'logs'
MAX_LOG_ITEMS = 300
DEBUG_HOME_OPEN_KEY = 'debug_home_area_open'


def _log_key() -> str:
    try:
        from bling_app_zero.v2.session_store import state_key
        return state_key('logs')
    except Exception:
        return LOG_SESSION_KEY


def _debug_open_key() -> str:
    try:
        from bling_app_zero.v2.session_store import state_key
        return state_key('debug_home_area_open')
    except Exception:
        return DEBUG_HOME_OPEN_KEY


def _safe_text(value: Any, limit: int = 1000) -> str:
    text = str(value or '').replace('\x00', '').strip()
    return text[:limit] + '...' if len(text) > limit else text


def _short_path(path: str | None) -> str:
    if not path:
        return ''
    normalized = str(path).replace('\\', '/')
    marker = '/bling_app_zero/'
    if marker in normalized:
        return 'bling_app_zero/' + normalized.split(marker, 1)[1]
    return Path(normalized).name or normalized[-120:]


def _summarize_value(value: Any) -> str:
    if value is None:
        return 'None'
    if isinstance(value, (bool, int, float)):
        return str(value)
    if isinstance(value, str):
        return _safe_text(value, 120)
    if hasattr(value, 'shape'):
        try:
            return f'DataFrame{tuple(value.shape)}'
        except Exception:
            return type(value).__name__
    if isinstance(value, dict):
        return f'dict({len(value)})'
    if isinstance(value, (list, tuple, set)):
        return f'{type(value).__name__}({len(value)})'
    return type(value).__name__


def _collect_state_context(keys: list[str] | tuple[str, ...] | set[str] | None) -> dict[str, str]:
    if not keys:
        return {}
    context: dict[str, str] = {}
    for key in list(keys)[:30]:
        text_key = str(key or '').strip()
        if not text_key or text_key not in st.session_state:
            continue
        try:
            context[text_key] = _summarize_value(st.session_state.get(text_key))
        except Exception:
            context[text_key] = '[erro ao resumir]'
    return context


def add_debug(
    message: str,
    origin: str = 'SISTEMA',
    level: str = 'INFO',
    *,
    file_name: str | None = None,
    state_keys: list[str] | tuple[str, ...] | set[str] | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    key = _log_key()
    logs = st.session_state.get(key, [])
    if not isinstance(logs, list):
        logs = []
    logs.append(
        {
            'hora': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'nivel': _safe_text(level or 'INFO', 40).upper(),
            'origem': _safe_text(origin or 'SISTEMA', 80),
            'arquivo': _short_path(file_name),
            'funcao': '',
            'linha': '',
            'estado': _collect_state_context(state_keys),
            'detalhes': details or {},
            'mensagem': _safe_text(message or ''),
        }
    )
    if len(logs) > MAX_LOG_ITEMS:
        del logs[:-MAX_LOG_ITEMS]
    st.session_state[key] = logs


def _format_context(context: dict[str, Any]) -> str:
    if not context:
        return ''
    try:
        return _safe_text(json.dumps(context, ensure_ascii=False, default=str), 1000)
    except Exception:
        return _safe_text(context, 1000)


def _logs_to_text(logs: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for item in logs:
        base = f"[{item.get('hora')}] [{item.get('nivel')}] [{item.get('origem')}]"
        arquivo = item.get('arquivo') or ''
        location = f' [{arquivo}]' if arquivo else ''
        message = item.get('mensagem', '')
        extras = []
        if item.get('estado'):
            extras.append(f"estado={_format_context(item.get('estado') or {})}")
        if item.get('detalhes'):
            extras.append(f"detalhes={_format_context(item.get('detalhes') or {})}")
        extra = ' | ' + ' | '.join(extras) if extras else ''
        lines.append(f'{base}{location} {message}{extra}')
    return '\n'.join(lines)


def _render_debug_actions(logs: list[dict[str, Any]], prefix: str = 'debug') -> None:
    key = _log_key()
    if st.button('Limpar logs', use_container_width=True, key=f'{prefix}_clear_logs'):
        st.session_state[key] = []
        st.success('Logs limpos.')
        st.rerun()

    if logs:
        st.download_button(
            'Baixar log debug',
            data=_logs_to_text(logs).encode('utf-8'),
            file_name='bling_debug.log',
            mime='text/plain; charset=utf-8',
            use_container_width=True,
            key=f'{prefix}_download_debug_log_{len(logs)}',
        )
        st.download_button(
            'Baixar log técnico JSON',
            data=json.dumps(logs, ensure_ascii=False, indent=2, default=str).encode('utf-8'),
            file_name='bling_debug.json',
            mime='application/json; charset=utf-8',
            use_container_width=True,
            key=f'{prefix}_download_debug_json_{len(logs)}',
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
            arquivo = item.get('arquivo') or ''
            local = f' — {arquivo}' if arquivo else ''
            st.caption(f'[{level}] {origin}{local}: {message}')
            if item.get('estado'):
                st.json(item.get('estado'))
            if item.get('detalhes'):
                st.json(item.get('detalhes'))


def _render_debug_content(prefix: str = 'debug') -> None:
    logs = list(st.session_state.get(_log_key(), []))
    _render_debug_actions(logs, prefix=prefix)
    if not logs:
        st.caption('Nenhum evento registrado ainda.')
        return
    st.caption(f'{len(logs)} evento(s) registrado(s).')
    _render_recent_logs(logs, prefix=prefix)


def render_debug_compact_button() -> None:
    key = _debug_open_key()
    if st.button('⚙️', key='open_debug_home_area', help='Logs técnicos'):
        st.session_state[key] = not bool(st.session_state.get(key, False))


def render_debug_home_area() -> None:
    if not st.session_state.get(_debug_open_key(), False):
        return
    with st.container(border=True):
        st.markdown('##### Logs técnicos')
        _render_debug_content(prefix='debug_home')


def render_debug_home_button() -> None:
    render_debug_compact_button()
    render_debug_home_area()


def render_debug_panel() -> None:
    with st.sidebar:
        _render_debug_content(prefix='debug_sidebar')


__all__ = [
    'LOG_SESSION_KEY',
    'MAX_LOG_ITEMS',
    'add_debug',
    'render_debug_compact_button',
    'render_debug_home_area',
    'render_debug_home_button',
    'render_debug_panel',
]
