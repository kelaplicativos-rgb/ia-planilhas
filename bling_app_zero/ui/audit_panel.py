from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import (
    AUDIT_EXPORT_FILENAME,
    add_audit_event,
    audit_download_payload,
    clear_audit_events,
    get_audit_events,
    get_audit_session_id,
)


def render_audit_panel() -> None:
    """Painel de auditoria operacional da sessão atual."""
    events = get_audit_events()
    with st.sidebar:
        with st.expander('Audit trail operacional', expanded=False):
            st.caption('Registra movimentos importantes da sessão: cliques, etapas, ações, downloads e decisões do fluxo.')
            st.caption(f'Sessão auditável: `{get_audit_session_id()}`')
            st.caption(f'{len(events)} evento(s) operacional(is) registrado(s).')

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

            payload = audit_download_payload()
            st.download_button(
                'Baixar audit trail',
                data=payload,
                file_name=AUDIT_EXPORT_FILENAME,
                mime='application/x-ndjson; charset=utf-8',
                use_container_width=True,
                key=f'audit_download_{len(events)}',
                disabled=not bool(events),
            )

            if events:
                show = st.toggle('Ver últimos eventos', value=False, key='audit_show_recent')
                if show:
                    for event in events[-20:]:
                        st.caption(
                            f"[{event.get('timestamp')}] "
                            f"[{event.get('area')}] "
                            f"{event.get('action')} "
                            f"({event.get('status')})"
                        )


__all__ = ['render_audit_panel']
