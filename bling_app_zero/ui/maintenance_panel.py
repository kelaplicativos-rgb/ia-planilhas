from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import streamlit as st

from bling_app_zero.core.audit import add_audit_event, audit_download_payload, get_audit_events, get_audit_session_id
from bling_app_zero.core.cache_control import clear_streamlit_cache
from bling_app_zero.core.debug import LOG_SESSION_KEY

LOG_BUNDLE_FILENAME = 'bling_logs_completos.zip'
SENSITIVE_KEYWORDS = (
    'password',
    'senha',
    'secret',
    'token',
    'client_secret',
    'authorization',
    'cookie',
    'api_key',
    'apikey',
)

COMPACT_KEEP_ACTIONS = {
    'field_added',
    'field_changed',
    'field_removed',
    'button_clicked',
    'wizard_step_changed',
    'wizard_next_clicked',
    'wizard_back_clicked',
    'wizard_next_blocked',
    'operation_changed',
    'operation_auto_selected',
    'operation_auto_recognized',
    'flow_state_synced',
    'pricing_toggle_changed',
    'pricing_config_updated',
    'model_upload_received',
    'model_file_read_failed',
    'model_upload_without_supported_files',
    'model_upload_classified',
    'app_critical_error',
    'sidebar_tool_failed',
    'manual_checkpoint',
    'cache_cleared_manually',
    'technical_logs_cleared_manually',
}


def _logs_to_text(logs: list[dict]) -> str:
    return '\n'.join(
        f"[{item.get('hora')}] [{item.get('nivel')}] [{item.get('origem')}] {item.get('mensagem')}"
        for item in logs
    )


def _json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode('utf-8')


def _jsonl_bytes(items: list[dict[str, Any]]) -> bytes:
    lines = [json.dumps(item, ensure_ascii=False, default=str) for item in items]
    return ('\n'.join(lines) + ('\n' if lines else '')).encode('utf-8')


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key or '').strip().lower()
    return any(word in normalized for word in SENSITIVE_KEYWORDS)


def _state_value_summary(value: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {'type': type(value).__name__}

    if value is None:
        summary['empty'] = True
        return summary

    if hasattr(value, 'shape') and hasattr(value, 'columns'):
        try:
            summary['shape'] = tuple(value.shape)
            summary['columns'] = [str(col) for col in list(value.columns)[:80]]
        except Exception:
            pass
        return summary

    if isinstance(value, (list, tuple, set, dict, str)):
        try:
            summary['length'] = len(value)
        except Exception:
            pass

    if isinstance(value, (bool, int, float)):
        summary['value'] = value
    elif isinstance(value, str):
        summary['preview'] = value[:180]

    return summary


def _session_state_summary() -> dict[str, Any]:
    state: dict[str, Any] = {}
    for key, value in st.session_state.items():
        text_key = str(key)
        if _is_sensitive_key(text_key):
            state[text_key] = {'type': type(value).__name__, 'value': '[REDACTED]'}
        else:
            state[text_key] = _state_value_summary(value)
    return state


def _event_signature(event: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(event.get('area') or ''),
        str(event.get('step') or ''),
        str(event.get('action') or ''),
        json.dumps(event.get('details') or {}, ensure_ascii=False, sort_keys=True, default=str),
    )


def _compact_audit_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compacted: list[dict[str, Any]] = []
    seen_render_events: set[tuple[str, str, str, str]] = set()

    for index, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            continue
        action = str(event.get('action') or '')
        normalized = dict(event)
        normalized.setdefault('event_id', index)

        if action in COMPACT_KEEP_ACTIONS or action.startswith('field_'):
            compacted.append(normalized)
            continue

        signature = _event_signature(normalized)
        if signature in seen_render_events:
            continue
        seen_render_events.add(signature)
        compacted.append(normalized)

    return compacted


def _build_log_bundle_zip() -> bytes:
    logs = list(st.session_state.get(LOG_SESSION_KEY, []))
    audit_events = get_audit_events()
    compact_events = _compact_audit_events(audit_events)
    generated_at = datetime.now().isoformat(timespec='seconds')

    manifest = {
        'generated_at': generated_at,
        'audit_session_id': get_audit_session_id(),
        'files': [
            'bling_debug.log',
            'bling_debug.json',
            'bling_audit_trail.jsonl',
            'bling_audit_trail_compacto.jsonl',
            'bling_session_state_summary.json',
            'manifest.json',
        ],
        'counts': {
            'technical_logs': len(logs),
            'audit_events_raw': len(audit_events),
            'audit_events_compact': len(compact_events),
            'session_state_keys': len(st.session_state.keys()),
        },
        'responsible_file': 'bling_app_zero/ui/maintenance_panel.py',
    }

    buffer = BytesIO()
    with ZipFile(buffer, mode='w', compression=ZIP_DEFLATED) as zip_file:
        zip_file.writestr('bling_debug.log', _logs_to_text(logs).encode('utf-8'))
        zip_file.writestr('bling_debug.json', _json_bytes(logs))
        zip_file.writestr('bling_audit_trail.jsonl', audit_download_payload())
        zip_file.writestr('bling_audit_trail_compacto.jsonl', _jsonl_bytes(compact_events))
        zip_file.writestr('bling_session_state_summary.json', _json_bytes(_session_state_summary()))
        zip_file.writestr('manifest.json', _json_bytes(manifest))
    return buffer.getvalue()


def _render_cache_tools() -> None:
    st.markdown('###### Cache')
    st.caption('Limpa cache interno do Streamlit sem apagar o fluxo atual do usuário.')
    if st.button('Limpar cache agora', use_container_width=True, key='maintenance_clear_cache_now'):
        clear_streamlit_cache(reason='manual_sidebar_maintenance')
        add_audit_event('cache_cleared_manually', area='CACHE', details={'source': 'maintenance_panel'})
        st.success('Cache limpo. Recarregando...')
        st.rerun()


def _render_log_bundle_download(logs: list[dict]) -> None:
    audit_events = get_audit_events()
    has_any_log = bool(logs) or bool(audit_events)
    st.markdown('###### Pacote completo')
    st.caption('Baixa todos os logs da sessão em um único arquivo ZIP: debug, audit bruto, audit compacto e resumo seguro do estado.')
    st.download_button(
        '⬇️ Baixar todos os logs (.zip)',
        data=_build_log_bundle_zip(),
        file_name=LOG_BUNDLE_FILENAME,
        mime='application/zip',
        use_container_width=True,
        key=f'maintenance_download_all_logs_zip_{len(logs)}_{len(audit_events)}',
        disabled=not has_any_log,
    )


def _render_log_tools() -> None:
    logs = list(st.session_state.get(LOG_SESSION_KEY, []))
    st.markdown('###### Logs técnicos')
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button('Limpar logs', use_container_width=True, key='maintenance_clear_logs'):
            st.session_state[LOG_SESSION_KEY] = []
            add_audit_event('technical_logs_cleared_manually', area='LOGS', details={'source': 'maintenance_panel'})
            st.success('Logs limpos.')
            st.rerun()
    with col_b:
        st.download_button(
            'Baixar log debug',
            data=_logs_to_text(logs).encode('utf-8'),
            file_name='bling_debug.log',
            mime='text/plain; charset=utf-8',
            use_container_width=True,
            key=f'maintenance_download_debug_log_{len(logs)}',
            disabled=not bool(logs),
        )

    _render_log_bundle_download(logs)

    st.caption(f'{len(logs)} evento(s) técnico(s) registrado(s).')
    show_logs = st.toggle('Ver eventos técnicos', value=False, key='maintenance_show_recent_logs')
    if show_logs and logs:
        with st.container(border=True):
            for item in logs[-25:]:
                level = item.get('nivel', 'INFO')
                origin = item.get('origem', 'SISTEMA')
                message = item.get('mensagem', '')
                st.caption(f'[{level}] {origin}: {message}')


def render_maintenance_panel() -> None:
    with st.sidebar:
        with st.expander('Manutenção do sistema', expanded=True):
            _render_cache_tools()
            st.divider()
            _render_log_tools()


__all__ = ['render_maintenance_panel']
