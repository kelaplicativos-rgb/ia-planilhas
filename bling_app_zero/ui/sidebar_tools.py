from __future__ import annotations

import traceback
from collections.abc import Callable

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.debug import add_debug
from bling_app_zero.ui.audit_panel import render_audit_panel
from bling_app_zero.ui.diagnostics_panel import render_diagnostics_panel
from bling_app_zero.ui.layout.sidebar_theme import inject_sidebar_tools_theme
from bling_app_zero.ui.maintenance_panel import render_maintenance_panel
from bling_app_zero.ui.rules_panel import render_rules_panel

SidebarRenderer = Callable[[], None]

SIDEBAR_TOOL_KEY = 'sidebar_active_technical_tool'
SIDEBAR_TOOLS_OPEN_KEY = 'sidebar_tools_open_by_default'

SIDEBAR_TOOLS: tuple[tuple[str, SidebarRenderer], ...] = (
    ('Ferramentas de conferência', render_diagnostics_panel),
    ('Audit trail operacional', render_audit_panel),
    ('Manutenção do sistema', render_maintenance_panel),
    ('Regras e padrões', render_rules_panel),
)


def _render_sidebar_header() -> None:
    with st.sidebar:
        st.markdown(
            """
            <section class="bling-sidebar-hero" aria-label="Ferramentas do sistema">
                <div class="bling-sidebar-kicker">Painel técnico</div>
                <div class="bling-sidebar-title">Ferramentas do sistema</div>
                <div class="bling-sidebar-text">Conferência, audit trail, manutenção e regras do CSV em módulos separados.</div>
            </section>
            """,
            unsafe_allow_html=True,
        )


def _render_sidebar_tool(name: str, renderer: SidebarRenderer) -> None:
    """Executa uma ferramenta da sidebar sem deixar uma falha derrubar as demais."""
    try:
        renderer()
    except Exception as exc:
        formatted = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        add_debug(f'Falha no módulo da sidebar {name}: {exc}', origin='SIDEBAR', level='ERRO')
        add_debug(formatted, origin='TRACEBACK', level='ERRO')
        add_audit_event(
            'sidebar_tool_failed',
            area='SIDEBAR',
            status='ERRO',
            details={'tool': name, 'error': str(exc), 'responsible_file': 'bling_app_zero/ui/sidebar_tools.py'},
        )
        with st.sidebar:
            with st.expander(f'{name} indisponível', expanded=True):
                st.error(f'O módulo {name} falhou, mas os outros recursos continuam disponíveis.')
                st.caption('Baixe o log técnico e envie para o próximo BLINGFIX.')


def _ensure_sidebar_defaults() -> None:
    if SIDEBAR_TOOLS_OPEN_KEY not in st.session_state:
        st.session_state[SIDEBAR_TOOLS_OPEN_KEY] = False
    if SIDEBAR_TOOL_KEY not in st.session_state:
        st.session_state[SIDEBAR_TOOL_KEY] = 'Ferramentas carregadas e recolhidas'


def render_sidebar_tools() -> None:
    """Renderiza a sidebar técnica com todas as ferramentas carregadas e recolhidas por padrão."""
    inject_sidebar_tools_theme()
    _ensure_sidebar_defaults()
    _render_sidebar_header()

    add_audit_event(
        'sidebar_tools_rendered',
        area='SIDEBAR',
        details={
            'mode': 'all_tools_loaded_collapsed',
            'tools': [name for name, _ in SIDEBAR_TOOLS],
            'responsible_file': 'bling_app_zero/ui/sidebar_tools.py',
        },
    )

    for name, renderer in SIDEBAR_TOOLS:
        _render_sidebar_tool(name, renderer)


__all__ = ['render_sidebar_tools']
