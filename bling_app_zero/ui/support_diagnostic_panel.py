from __future__ import annotations

from datetime import datetime

import streamlit as st

from bling_app_zero.core.audit import add_audit_event, get_audit_events
from bling_app_zero.core.debug import LOG_SESSION_KEY
from bling_app_zero.ui.maintenance_panel import LOG_BUNDLE_FILENAME, _build_log_bundle_zip

DIAGNOSTIC_READY_KEY = 'support_diagnostic_ready_v2'
DIAGNOSTIC_BYTES_KEY = 'support_diagnostic_bytes_v2'
DIAGNOSTIC_TIME_KEY = 'support_diagnostic_time_v2'

RESPONSIBLE_FILE = 'bling_app_zero/ui/support_diagnostic_panel.py'


def _prepare_diagnostic() -> None:
    logs = list(st.session_state.get(LOG_SESSION_KEY, []))
    audit_events = get_audit_events()
    add_audit_event(
        'support_diagnostic_requested',
        area='SIDEBAR',
        details={
            'technical_logs': len(logs),
            'audit_events': len(audit_events),
            'session_state_keys': len(st.session_state.keys()),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    data = _build_log_bundle_zip()
    st.session_state[DIAGNOSTIC_BYTES_KEY] = data
    st.session_state[DIAGNOSTIC_READY_KEY] = True
    st.session_state[DIAGNOSTIC_TIME_KEY] = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    add_audit_event(
        'support_diagnostic_ready',
        area='SIDEBAR',
        details={'size_bytes': len(data), 'responsible_file': RESPONSIBLE_FILE},
    )


def render_support_diagnostic_panel() -> None:
    """Painel mínimo: não monta o ZIP durante a inicialização."""
    with st.sidebar:
        with st.expander('Enviar diagnóstico para suporte', expanded=False):
            st.caption('Se algo der erro, gere o diagnóstico e envie o arquivo no BLINGFIX.')
            if st.button('Gerar diagnóstico', use_container_width=True, key='support_diagnostic_prepare_button'):
                _prepare_diagnostic()
                st.rerun()

            if not st.session_state.get(DIAGNOSTIC_READY_KEY):
                return

            generated_at = st.session_state.get(DIAGNOSTIC_TIME_KEY, 'agora')
            st.success(f'Diagnóstico pronto em {generated_at}.')
            st.download_button(
                '⬇️ Baixar diagnóstico completo',
                data=st.session_state.get(DIAGNOSTIC_BYTES_KEY, b''),
                file_name=LOG_BUNDLE_FILENAME,
                mime='application/zip',
                use_container_width=True,
                key='support_diagnostic_download_button',
            )


__all__ = ['render_support_diagnostic_panel']
