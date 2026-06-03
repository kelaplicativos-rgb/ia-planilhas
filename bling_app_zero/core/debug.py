from __future__ import annotations

import importlib
import json
from collections.abc import MutableMapping
from datetime import datetime
from pathlib import Path
from typing import Any

LOG_SESSION_KEY = 'logs'
MAX_LOG_ITEMS = 120
DEBUG_HOME_OPEN_KEY = 'debug_home_area_open'
_FALLBACK_STATE: dict[str, Any] = {}


def _streamlit_module() -> Any | None:
    try:
        return importlib.import_module('streamlit')
    except Exception:
        return None


def _state_store() -> MutableMapping[str, Any]:
    st = _streamlit_module()
    if st is not None:
        try:
            return st.session_state
        except Exception:
            pass
    return _FALLBACK_STATE


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


def _collect_state_context(keys: list[str] | tuple[str, ...] | set[str] | None, *, state: MutableMapping[str, Any] | None = None) -> dict[str, str]:
    if not keys:
        return {}
    store = state if state is not None else _state_store()
    context: dict[str, str] = {}
    for key in list(keys)[:20]:
        text_key = str(key or '').strip()
        if not text_key or text_key not in store:
            continue
        try:
            context[text_key] = _summarize_value(store.get(text_key))
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
    state: MutableMapping[str, Any] | None = None,
) -> None:
    store = state if state is not None else _state_store()
    key = _log_key()
    logs = store.get(key, [])
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
            'estado': _collect_state_context(state_keys, state=store),
            'detalhes': details or {},
            'mensagem': _safe_text(message or ''),
        }
    )
    if len(logs) > MAX_LOG_ITEMS:
        del logs[:-MAX_LOG_ITEMS]
    store[key] = logs


def get_debug_logs(state: MutableMapping[str, Any] | None = None) -> list[dict[str, Any]]:
    store = state if state is not None else _state_store()
    logs = store.get(_log_key(), [])
    return list(logs) if isinstance(logs, list) else []


def clear_debug_logs(state: MutableMapping[str, Any] | None = None) -> None:
    store = state if state is not None else _state_store()
    store[_log_key()] = []


def logs_to_text(logs: list[dict[str, Any]]) -> str:
    return _logs_to_text(logs)


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
    st = _streamlit_module()
    if st is None:
        return
    if st.button('Limpar logs', use_container_width=True, key=f'{prefix}_clear_logs'):
        clear_debug_logs()
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
    st = _streamlit_module()
    if st is None:
        return
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
    st = _streamlit_module()
    if st is None:
        return
    logs = get_debug_logs()
    _render_debug_actions(logs, prefix=prefix)
    if not logs:
        st.caption('Nenhum evento registrado ainda.')
        return
    st.caption(f'{len(logs)} evento(s) registrado(s).')
    _render_recent_logs(logs, prefix=prefix)


def render_debug_compact_button() -> None:
    st = _streamlit_module()
    if st is None:
        return
    store = _state_store()
    key = _debug_open_key()
    if st.button('⚙️', key='open_debug_home_area', help='Logs técnicos'):
        store[key] = not bool(store.get(key, False))


def render_debug_home_area() -> None:
    st = _streamlit_module()
    if st is None:
        return
    store = _state_store()
    if not store.get(_debug_open_key(), False):
        return
    with st.container(border=True):
        st.markdown('##### Logs técnicos')
        _render_debug_content(prefix='debug_home')


def render_debug_home_button() -> None:
    render_debug_compact_button()
    render_debug_home_area()


def render_debug_panel() -> None:
    st = _streamlit_module()
    if st is None:
        return
    with st.sidebar:
        _render_debug_content(prefix='debug_sidebar')


__all__ = [
    'LOG_SESSION_KEY',
    'MAX_LOG_ITEMS',
    'add_debug',
    'clear_debug_logs',
    'get_debug_logs',
    'logs_to_text',
    'render_debug_home_button',
    'render_debug_panel',
]
