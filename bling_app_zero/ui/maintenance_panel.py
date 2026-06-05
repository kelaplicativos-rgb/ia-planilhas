from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import streamlit as st

from bling_app_zero.core.audit import add_audit_event, audit_download_payload, get_audit_events, get_audit_session_id
from bling_app_zero.core.debug import LOG_SESSION_KEY
from bling_app_zero.core.system_inventory import inventory_markdown, inventory_payload, inventory_summary

LOG_BUNDLE_FILENAME = 'bling_diagnostico_completo.zip'
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
    'home_stale_flow_cleared',
    'home_operation_selected',
    'home_operation_cleared',
    'app_critical_error',
    'sidebar_tool_failed',
    'manual_checkpoint',
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
            summary['columns'] = [str(col) for col in list(value.columns)[:100]]
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
        summary['preview'] = value[:220]

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
    inventory = inventory_payload()

    manifest = {
        'generated_at': generated_at,
        'audit_session_id': get_audit_session_id(),
        'files': [
            'bling_debug.log',
            'bling_debug.json',
            'bling_audit_trail.jsonl',
            'bling_audit_trail_compacto.jsonl',
            'bling_session_state_summary.json',
            'bling_system_inventory.json',
            'bling_system_inventory.md',
            'manifest.json',
        ],
        'counts': {
            'technical_logs': len(logs),
            'audit_events_raw': len(audit_events),
            'audit_events_compact': len(compact_events),
            'session_state_keys': len(st.session_state.keys()),
            'system_inventory_total': int(inventory.get('summary', {}).get('total_subsystems') or 0),
            'system_inventory_active': int(inventory.get('summary', {}).get('active_subsystems') or 0),
            'system_inventory_risk': int(inventory.get('summary', {}).get('risk_subsystems') or 0),
        },
        'system_inventory_summary': inventory_summary(),
        'observacao': 'Pacote seguro para enviar no BLINGFIX. Chaves sensíveis são mascaradas no resumo do estado.',
        'responsible_file': 'bling_app_zero/ui/maintenance_panel.py',
    }

    buffer = BytesIO()
    with ZipFile(buffer, mode='w', compression=ZIP_DEFLATED) as zip_file:
        zip_file.writestr('bling_debug.log', _logs_to_text(logs).encode('utf-8'))
        zip_file.writestr('bling_debug.json', _json_bytes(logs))
        zip_file.writestr('bling_audit_trail.jsonl', audit_download_payload())
        zip_file.writestr('bling_audit_trail_compacto.jsonl', _jsonl_bytes(compact_events))
        zip_file.writestr('bling_session_state_summary.json', _json_bytes(_session_state_summary()))
        zip_file.writestr('bling_system_inventory.json', _json_bytes(inventory))
        zip_file.writestr('bling_system_inventory.md', inventory_markdown().encode('utf-8'))
        zip_file.writestr('manifest.json', _json_bytes(manifest))
    return buffer.getvalue()


def render_maintenance_panel() -> None:
    """Sidebar mínima: apenas o arquivo que o usuário precisa enviar no BLINGFIX."""
    logs = list(st.session_state.get(LOG_SESSION_KEY, []))
    audit_events = get_audit_events()
    has_diagnostic_data = bool(logs) or bool(audit_events) or bool(st.session_state.keys())

    with st.sidebar:
        with st.expander('Enviar diagnóstico para suporte', expanded=False):
            st.caption('Se algo der erro, baixe este arquivo e envie no BLINGFIX.')
            st.download_button(
                '⬇️ Baixar diagnóstico completo',
                data=_build_log_bundle_zip(),
                file_name=LOG_BUNDLE_FILENAME,
                mime='application/zip',
                use_container_width=True,
                key=f'maintenance_download_support_diagnostic_zip_{len(logs)}_{len(audit_events)}_{len(st.session_state.keys())}',
                disabled=not has_diagnostic_data,
            )
            add_audit_event(
                'support_diagnostic_panel_rendered',
                area='SIDEBAR',
                details={
                    'mode': 'minimal_download_only',
                    'technical_logs': len(logs),
                    'audit_events': len(audit_events),
                    'session_state_keys': len(st.session_state.keys()),
                    'system_inventory': inventory_summary(),
                    'responsible_file': 'bling_app_zero/ui/maintenance_panel.py',
                },
            )


__all__ = ['render_maintenance_panel']
