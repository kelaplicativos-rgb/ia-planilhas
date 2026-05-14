from __future__ import annotations

from datetime import datetime

import streamlit as st

from bling_app_zero.core.audit import add_audit_event, get_audit_events
from bling_app_zero.core.debug import LOG_SESSION_KEY
from bling_app_zero.ui.maintenance_panel import LOG_BUNDLE_FILENAME, _build_log_bundle_zip

RESPONSIBLE_FILE = 'bling_app_zero/ui/support_diagnostic_panel.py'
DIAGNOSTIC_BYTES_KEY = 'support_diagnostic_zip_bytes'
DIAGNOSTIC_READY_KEY = 'support_diagnostic_zip_ready'
DIAGNOSTIC_TIME_KEY = 'support_diagnostic_zip_generated_at'


def _prepare_diagnostic_zip() -> None:
    logs = list(st.session_state.get(LOG_SESSION_KEY, []))
    audit_events = get_audit_events()
    data = _build_log_bundle_zip()

    st.session_state[DIAGNOSTIC_BYTES_KEY] = data
    st.session_state[DIAGNOSTIC_READY_KEY] = True
    st.session_state[DIAGNOSTIC_TIME_KEY] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')

    add_audit_event(
        'support_diagnostic_zip_generated',
        area='SIDEBAR',
        details={
            'technical_logs': len(logs),
            'audit_events': len(audit_events),
            'session_state_keys': len(st.session_state.keys()),
            'zip_size_bytes': len(data),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def render_support_diagnostic_panel() -> None:
    """Sidebar leve: o ZIP só é montado depois do clique do usuário."""
    with st.sidebar:
        if st.button(
            '⬇️ Gerar diagnóstico para correção',
            use_container_width=True,
            key='support_diagnostic_generate_button',
        ):
            _prepare_diagnostic_zip()
            st.rerun()

        if not st.session_state.get(DIAGNOSTIC_READY_KEY):
            return

        generated_at = st.session_state.get(DIAGNOSTIC_TIME_KEY, 'agora')
        st.caption(f'Diagnóstico pronto: {generated_at}')
        st.download_button(
            'Baixar arquivo gerado',
            data=st.session_state.get(DIAGNOSTIC_BYTES_KEY, b''),
            file_name=LOG_BUNDLE_FILENAME,
            mime='application/zip',
            use_container_width=True,
            key='support_diagnostic_download_ready_button',
        )


__all__ = ['render_support_diagnostic_panel']
