from __future__ import annotations

import traceback
from collections.abc import Callable
from dataclasses import dataclass

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.debug import add_debug
from bling_app_zero.ui.layout.sidebar_theme import inject_sidebar_tools_theme

SidebarRenderer = Callable[[], None]

SIDEBAR_TOOL_KEY = 'sidebar_active_technical_tool'
SIDEBAR_TOOLS_OPEN_KEY = 'sidebar_tools_open_by_default'


@dataclass(frozen=True)
class SidebarTool:
    name: str
    renderer: SidebarRenderer


def _render_support_diagnostic_panel_lazy() -> None:
    from bling_app_zero.ui.support_diagnostic_panel import render_support_diagnostic_panel

    render_support_diagnostic_panel()


SIDEBAR_TOOLS: tuple[SidebarTool, ...] = (
    SidebarTool('Enviar diagnóstico para suporte', _render_support_diagnostic_panel_lazy),
)


def _render_sidebar_header() -> None:
    with st.sidebar:
        st.markdown(
            """
            <section class="bling-sidebar-hero" aria-label="Suporte técnico">
                <div class="bling-sidebar-kicker">Suporte</div>
                <div class="bling-sidebar-title">Enviar diagnóstico</div>
                <div class="bling-sidebar-text">Gere um pacote único com logs, auditoria e estado seguro da sessão para enviar no BLINGFIX.</div>
            </section>
            """,
            unsafe_allow_html=True,
        )


def _render_sidebar_tool(name: str, renderer: SidebarRenderer) -> None:
    """Executa a ferramenta essencial da sidebar sem derrubar o app."""
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
            with st.expander('Diagnóstico indisponível', expanded=True):
                st.error('Não consegui montar o pacote técnico, mas o sistema principal continua aberto.')
                st.caption('Tire um print desta tela e envie no próximo BLINGFIX.')


def _ensure_sidebar_defaults() -> None:
    if SIDEBAR_TOOLS_OPEN_KEY not in st.session_state:
        st.session_state[SIDEBAR_TOOLS_OPEN_KEY] = False
    if SIDEBAR_TOOL_KEY not in st.session_state:
        st.session_state[SIDEBAR_TOOL_KEY] = 'Diagnóstico técnico recolhido'


def _clear_legacy_sidebar_rules_state() -> None:
    legacy_keys = [
        'sidebar_rules_center_requested',
        'sidebar_open_rules_center_inline',
        'bling_command_center_prompt',
        'bling_command_center_command_name',
        'bling_command_center_last_run',
        'sidebar_active_technical_tool',
        'show_engine_inventory',
        'openai_validation_result',
        'blingflow_simulation_result',
        'blingscan_prompt_ready',
        'blingscan_prompt_last_run',
    ]
    removed: list[str] = []
    for key in legacy_keys:
        if key in st.session_state:
            removed.append(key)
            st.session_state.pop(key, None)
    if removed:
        add_audit_event(
            'legacy_sidebar_noise_state_cleared',
            area='SIDEBAR',
            details={'removed_keys': removed, 'responsible_file': 'bling_app_zero/ui/sidebar_tools.py'},
        )


def render_sidebar_tools() -> None:
    inject_sidebar_tools_theme()
    _ensure_sidebar_defaults()
    _clear_legacy_sidebar_rules_state()
    _render_sidebar_header()

    add_audit_event(
        'sidebar_tools_rendered',
        area='SIDEBAR',
        details={
            'mode': 'minimal_support_diagnostic_on_demand',
            'removed_panels': [
                'BLINGSCAN automático',
                'Assistente IA de correção',
                'Ferramentas de conferência',
                'Recursos disponíveis',
                'Lista de módulos e capacidades carregadas no sistema',
            ],
            'tools': [tool.name for tool in SIDEBAR_TOOLS],
            'responsible_file': 'bling_app_zero/ui/sidebar_tools.py',
        },
    )

    for tool in SIDEBAR_TOOLS:
        _render_sidebar_tool(tool.name, tool.renderer)


__all__ = ['render_sidebar_tools']
