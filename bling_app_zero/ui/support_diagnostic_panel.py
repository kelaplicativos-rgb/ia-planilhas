from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event, get_audit_events
from bling_app_zero.core.debug import LOG_SESSION_KEY
from bling_app_zero.ui.maintenance_panel import LOG_BUNDLE_FILENAME, _build_log_bundle_zip

RESPONSIBLE_FILE = 'bling_app_zero/ui/support_diagnostic_panel.py'


def render_support_diagnostic_panel() -> None:
    """Sidebar final: apenas um botão para baixar tudo que ajuda no BLINGFIX."""
    logs = list(st.session_state.get(LOG_SESSION_KEY, []))
    audit_events = get_audit_events()
    data = _build_log_bundle_zip()

    add_audit_event(
        'support_diagnostic_download_rendered',
        area='SIDEBAR',
        details={
            'technical_logs': len(logs),
            'audit_events': len(audit_events),
            'session_state_keys': len(st.session_state.keys()),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )

    with st.sidebar:
        st.download_button(
            '⬇️ Baixar diagnóstico para correção',
            data=data,
            file_name=LOG_BUNDLE_FILENAME,
            mime='application/zip',
            use_container_width=True,
            key='support_diagnostic_single_download_button',
        )


__all__ = ['render_support_diagnostic_panel']
