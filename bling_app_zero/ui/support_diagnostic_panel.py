from __future__ import annotations

from datetime import datetime

import streamlit as st

from bling_app_zero.core.audit import add_audit_event, get_audit_events
from bling_app_zero.core.support_diagnostic_runtime import build_support_diagnostic_zip, collect_dataframes, collect_debug_logs
from bling_app_zero.ui.home_wizard_rerun import safe_rerun
from bling_app_zero.ui.maintenance_panel import LOG_BUNDLE_FILENAME

RESPONSIBLE_FILE = 'bling_app_zero/ui/support_diagnostic_panel.py'
DIAGNOSTIC_BYTES_KEY = 'support_diagnostic_zip_bytes'
DIAGNOSTIC_READY_KEY = 'support_diagnostic_zip_ready'
DIAGNOSTIC_TIME_KEY = 'support_diagnostic_zip_generated_at'


def _normalize_namespace(namespace: str) -> str:
    text = str(namespace or '').strip().lower()
    safe = ''.join(char if char.isalnum() else '_' for char in text)
    return safe.strip('_') or 'default'


def _widget_key(namespace: str, name: str) -> str:
    return f'support_diagnostic_{_normalize_namespace(namespace)}_{name}'


def _prepare_diagnostic_zip(*, source: str = 'sidebar') -> None:
    logs = collect_debug_logs()
    audit_events = get_audit_events()
    dataframes = collect_dataframes()
    data = build_support_diagnostic_zip()

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
            'diagnostic_dataframes': len(dataframes),
            'zip_size_bytes': len(data),
            'source': source,
            'responsible_file': RESPONSIBLE_FILE,
            'blingfix': 'runtime_diagnostic_zip_with_namespaced_logs_and_dataframe_samples',
        },
    )


def render_support_diagnostic_panel_content(*, namespace: str = 'default') -> None:
    """Conteúdo reutilizável do diagnóstico, sem abrir outro bloco de sidebar.

    BLINGFIX: este painel pode aparecer em mais de uma área da sidebar no mesmo
    ciclo de renderização. Por isso os widgets recebem namespace próprio para
    evitar erro de chave duplicada no Streamlit.
    """
    widget_namespace = _normalize_namespace(namespace)
    if st.button(
        '⬇️ Gerar diagnóstico para correção',
        use_container_width=True,
        key=_widget_key(widget_namespace, 'generate_button'),
    ):
        _prepare_diagnostic_zip(source=widget_namespace)
        safe_rerun(f'support_diagnostic_zip_generated_{widget_namespace}')

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
        key=_widget_key(widget_namespace, 'download_ready_button'),
    )


def render_support_diagnostic_panel() -> None:
    """Compatibilidade: mantém o render antigo quando chamado isoladamente."""
    with st.sidebar:
        render_support_diagnostic_panel_content(namespace='sidebar_tools')


__all__ = ['render_support_diagnostic_panel', 'render_support_diagnostic_panel_content']
