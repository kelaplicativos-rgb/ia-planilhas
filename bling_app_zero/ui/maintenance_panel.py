from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event, get_audit_events
from bling_app_zero.core.support_diagnostic_runtime import build_support_diagnostic_zip, collect_dataframes, collect_debug_logs
from bling_app_zero.core.system_inventory_runtime import inventory_summary

LOG_BUNDLE_FILENAME = 'bling_diagnostico_completo.zip'


def _build_log_bundle_zip() -> bytes:
    """Mantém compatibilidade com importações antigas do painel de manutenção."""
    return build_support_diagnostic_zip()


def render_maintenance_panel() -> None:
    """Painel legado redirecionado para o runtime oficial de diagnóstico."""
    logs = collect_debug_logs()
    audit_events = get_audit_events()
    dataframes = collect_dataframes()
    has_diagnostic_data = bool(logs) or bool(audit_events) or bool(st.session_state.keys()) or bool(dataframes)

    with st.sidebar:
        with st.expander('Enviar diagnóstico para suporte', expanded=False):
            st.caption('Se algo der erro, baixe este arquivo e envie no BLINGFIX.')
            st.download_button(
                '⬇️ Baixar diagnóstico completo',
                data=_build_log_bundle_zip(),
                file_name=LOG_BUNDLE_FILENAME,
                mime='application/zip',
                use_container_width=True,
                key=f'maintenance_download_support_diagnostic_zip_{len(logs)}_{len(audit_events)}_{len(st.session_state.keys())}_{len(dataframes)}',
                disabled=not has_diagnostic_data,
            )
            add_audit_event(
                'support_diagnostic_panel_rendered',
                area='SIDEBAR',
                details={
                    'mode': 'legacy_redirected_to_runtime',
                    'technical_logs': len(logs),
                    'audit_events': len(audit_events),
                    'session_state_keys': len(st.session_state.keys()),
                    'diagnostic_dataframes': len(dataframes),
                    'system_inventory': inventory_summary(),
                    'responsible_file': 'bling_app_zero/ui/maintenance_panel.py',
                    'blingclean': 'legacy_diagnostic_path_removed',
                },
            )


__all__ = ['LOG_BUNDLE_FILENAME', 'render_maintenance_panel', '_build_log_bundle_zip']
