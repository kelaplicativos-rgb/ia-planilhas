from __future__ import annotations

import json
from typing import Any

import streamlit as st

from bling_app_zero.core.audit import (
    AUDIT_EXPORT_FILENAME,
    add_audit_event,
    audit_download_payload,
    clear_audit_events,
    get_audit_events,
    get_audit_session_id,
)

AUDIT_COMPACT_EXPORT_FILENAME = 'bling_audit_trail_compacto.jsonl'
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
}


def _event_signature(event: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(event.get('area') or ''),
        str(event.get('step') or ''),
        str(event.get('action') or ''),
        json.dumps(event.get('details') or {}, ensure_ascii=False, sort_keys=True, default=str),
    )


def _compact_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
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


def _compact_download_payload(events: list[dict[str, Any]]) -> bytes:
    compacted = _compact_events(events)
    lines = [json.dumps(event, ensure_ascii=False, default=str) for event in compacted]
    return ('\n'.join(lines) + ('\n' if lines else '')).encode('utf-8')


def _render_recent_events(events: list[dict[str, Any]], compact: bool) -> None:
    visible_events = _compact_events(events) if compact else events
    for event in visible_events[-20:]:
        st.caption(
            f"[{event.get('timestamp')}] "
            f"[{event.get('area')}] "
            f"{event.get('action')} "
            f"({event.get('status')})"
        )


def render_audit_panel() -> None:
    """Painel de auditoria operacional da sessão atual."""
    events = get_audit_events()
    compact_events = _compact_events(events)
    with st.sidebar:
        with st.expander('Audit trail operacional', expanded=False):
            st.caption('Registra movimentos importantes da sessão: cliques, etapas, ações, downloads e decisões do fluxo.')
            st.caption(f'Sessão auditável: `{get_audit_session_id()}`')
            st.caption(f'{len(events)} evento(s) bruto(s) · {len(compact_events)} evento(s) no compacto.')

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button('Limpar audit', use_container_width=True, key='audit_clear_events'):
                    clear_audit_events()
                    st.success('Audit trail limpo.')
                    st.rerun()
            with col_b:
                if st.button('Registrar marco', use_container_width=True, key='audit_manual_checkpoint'):
                    add_audit_event('manual_checkpoint', area='AUDIT', details={'source': 'sidebar'})
                    st.success('Marco registrado.')
                    st.rerun()

            st.download_button(
                'Baixar audit trail bruto',
                data=audit_download_payload(),
                file_name=AUDIT_EXPORT_FILENAME,
                mime='application/x-ndjson; charset=utf-8',
                use_container_width=True,
                key=f'audit_download_raw_{len(events)}',
                disabled=not bool(events),
            )

            st.download_button(
                'Baixar audit compacto para análise',
                data=_compact_download_payload(events),
                file_name=AUDIT_COMPACT_EXPORT_FILENAME,
                mime='application/x-ndjson; charset=utf-8',
                use_container_width=True,
                key=f'audit_download_compact_{len(compact_events)}',
                disabled=not bool(events),
            )

            if events:
                show = st.toggle('Ver últimos eventos', value=False, key='audit_show_recent')
                if show:
                    compact_view = st.toggle(
                        'Ocultar repetições na visualização',
                        value=True,
                        key='audit_recent_compact_view',
                    )
                    _render_recent_events(events, compact=compact_view)


__all__ = ['render_audit_panel']
