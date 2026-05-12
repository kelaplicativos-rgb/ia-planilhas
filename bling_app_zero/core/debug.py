from __future__ import annotations

import inspect
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

LOG_SESSION_KEY = 'logs'
MAX_LOG_ITEMS = 300
DEBUG_HOME_OPEN_KEY = 'debug_home_area_open'

STATE_CONTEXT_KEYS = (
    'bling_wizard_step',
    'etapa',
    'etapa_fluxo',
    'etapa_origem',
    'operacao',
    'origem_dados',
    'tipo_operacao',
    'modo_operacao',
    'fluxo_operacao',
    'deposito_nome',
    'df_origem',
    'df_saida',
    'df_final',
    'df_precificado',
    'df_modelo_cadastro',
    'df_modelo_estoque',
    'modelo_cadastro_carregado',
    'modelo_estoque_carregado',
    'mapeamento_colunas',
    'mapeamento_confirmado',
)

PRIVATE_KEY_HINTS = (
    'senha',
    'token',
    'secret',
    'cookie',
    'apikey',
)


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


def _safe_text(value: Any, limit: int = 4000) -> str:
    text = str(value or '').replace('\x00', '').strip()
    if len(text) > limit:
        return text[:limit] + '...'
    return text


def _short_path(path: str | None) -> str:
    if not path:
        return ''

    normalized = str(path).replace('\\', '/')
    marker = '/bling_app_zero/'
    if marker in normalized:
        return 'bling_app_zero/' + normalized.split(marker, 1)[1]

    name = Path(normalized).name
    return name or normalized[-120:]


def _infer_caller_context() -> dict[str, str]:
    try:
        current_file = Path(__file__).resolve()

        for frame in inspect.stack()[2:12]:
            filename = frame.filename or ''
            if not filename:
                continue

            try:
                frame_file = Path(filename).resolve()
            except Exception:
                frame_file = Path(filename)

            if frame_file == current_file:
                continue

            return {
                'arquivo': _short_path(str(frame_file)),
                'funcao': _safe_text(frame.function or '', 120),
                'linha': str(frame.lineno or ''),
            }
    except Exception:
        pass

    return {
        'arquivo': '',
        'funcao': '',
        'linha': '',
    }


def _is_private_key(key: Any) -> bool:
    normalized = str(key or '').strip().lower()
    return any(word in normalized for word in PRIVATE_KEY_HINTS)


def _value_summary(value: Any) -> str:
    if value is None:
        return 'None'

    if isinstance(value, bool):
        return str(value)

    if isinstance(value, (int, float)):
        return str(value)

    if isinstance(value, str):
        return _safe_text(value, 140)

    if hasattr(value, 'shape') and hasattr(value, 'columns'):
        try:
            rows, cols = value.shape
            col_names = [_safe_text(col, 60) for col in list(value.columns)[:8]]
            extra = ', ...' if len(getattr(value, 'columns', [])) > 8 else ''
            return f'DataFrame({rows}x{cols}) cols=[{", ".join(col_names)}{extra}]'
        except Exception:
            return type(value).__name__

    if isinstance(value, dict):
        keys = list(value.keys())
        preview = [_safe_text(key, 60) for key in keys[:8]]
        extra = ', ...' if len(keys) > 8 else ''
        return f'dict({len(keys)}) keys=[{", ".join(preview)}{extra}]'

    if isinstance(value, (list, tuple, set)):
        return f'{type(value).__name__}({len(value)})'

    return _safe_text(type(value).__name__, 120)


def _collect_state_context(extra_keys: list[str] | tuple[str, ...] | set[str] | None = None) -> dict[str, str]:
    keys: list[str] = list(STATE_CONTEXT_KEYS)

    if extra_keys:
        for key in extra_keys:
            text_key = str(key or '').strip()
            if text_key and text_key not in keys:
                keys.append(text_key)

    context: dict[str, str] = {}

    for key in keys:
        if key not in st.session_state:
            continue

        if _is_private_key(key):
            context[key] = '[REDACTED]'
            continue

        try:
            context[key] = _value_summary(st.session_state.get(key))
        except Exception:
            context[key] = '[erro ao resumir]'

    return context


def _format_context_for_message(context: dict[str, Any]) -> str:
    if not context:
        return ''

    try:
        compact = json.dumps(context, ensure_ascii=False, default=str)
    except Exception:
        compact = str(context)

    return _safe_text(compact, 1800)


def add_debug(
    message: str,
    origin: str = 'SISTEMA',
    level: str = 'INFO',
    *,
    file_name: str | None = None,
    state_keys: list[str] | tuple[str, ...] | set[str] | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    caller = _infer_caller_context()

    if file_name:
        caller['arquivo'] = _short_path(file_name)

    key = _log_key()
    logs = list(st.session_state.get(key, []))
    logs.append(
        {
            'hora': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'nivel': _safe_text(level or 'INFO', 40).upper(),
            'origem': _safe_text(origin or 'SISTEMA', 80),
            'arquivo': _safe_text(caller.get('arquivo', ''), 160),
            'funcao': _safe_text(caller.get('funcao', ''), 120),
            'linha': _safe_text(caller.get('linha', ''), 20),
            'estado': _collect_state_context(state_keys),
            'detalhes': details or {},
            'mensagem': _safe_text(message or ''),
        }
    )
    st.session_state[key] = logs[-MAX_LOG_ITEMS:]


def _logs_to_text(logs: list[dict[str, Any]]) -> str:
    lines: list[str] = []

    for item in logs:
        base = (
            f"[{item.get('hora')}] "
            f"[{item.get('nivel')}] "
            f"[{item.get('origem')}]"
        )

        arquivo = item.get('arquivo') or ''
        funcao = item.get('funcao') or ''
        linha = item.get('linha') or ''

        location_parts = []
        if arquivo:
            location_parts.append(str(arquivo))
        if funcao:
            location_parts.append(f'função={funcao}')
        if linha:
            location_parts.append(f'linha={linha}')

        location = ''
        if location_parts:
            location = ' [' + ' | '.join(location_parts) + ']'

        mensagem = item.get('mensagem', '')
        estado = item.get('estado') or {}
        detalhes = item.get('detalhes') or {}

        extra_parts = []
        if estado:
            extra_parts.append(f'estado={_format_context_for_message(estado)}')
        if detalhes:
            extra_parts.append(f'detalhes={_format_context_for_message(detalhes)}')

        extra = ''
        if extra_parts:
            extra = ' | ' + ' | '.join(extra_parts)

        lines.append(f'{base}{location} {mensagem}{extra}')

    return '\n'.join(lines)


def _render_debug_actions(logs: list[dict[str, Any]], prefix: str = 'debug') -> None:
    key = _log_key()
    if st.button('Limpar logs', use_container_width=True, key=f'{prefix}_clear_logs'):
        st.session_state[key] = []
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

        json_payload = json.dumps(logs, ensure_ascii=False, indent=2, default=str)
        st.download_button(
            'Baixar log técnico JSON',
            data=json_payload.encode('utf-8'),
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
            funcao = item.get('funcao') or ''
            linha = item.get('linha') or ''

            local = ''
            if arquivo:
                local = f' — {arquivo}'
                if funcao:
                    local += f'::{funcao}'
                if linha:
                    local += f':{linha}'

            st.caption(f'[{level}] {origin}{local}: {message}')

            estado = item.get('estado') or {}
            if estado:
                with st.expander('Chaves de estado deste evento', expanded=False):
                    st.json(estado)

            detalhes = item.get('detalhes') or {}
            if detalhes:
                with st.expander('Detalhes técnicos deste evento', expanded=False):
                    st.json(detalhes)


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
        with st.expander('Logs técnicos', expanded=False):
            _render_debug_content(prefix='debug_sidebar')
