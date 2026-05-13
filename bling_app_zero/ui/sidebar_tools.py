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
    group: str
    renderer: SidebarRenderer


def _render_features_panel_lazy() -> None:
    from bling_app_zero.ui.features_panel import render_features_panel

    render_features_panel()


def _render_bling_command_center_lazy() -> None:
    from bling_app_zero.ui.bling_command_center import render_bling_command_center

    with st.sidebar:
        with st.expander('Comandos BLING prontos', expanded=False):
            render_bling_command_center()


def _render_diagnostics_panel_lazy() -> None:
    from bling_app_zero.ui.diagnostics_panel import render_diagnostics_panel

    render_diagnostics_panel()


def _render_ai_maintenance_panel_lazy() -> None:
    from bling_app_zero.ui.ai_maintenance_panel import render_ai_maintenance_panel

    render_ai_maintenance_panel()


def _render_maintenance_panel_lazy() -> None:
    from bling_app_zero.ui.maintenance_panel import render_maintenance_panel

    render_maintenance_panel()


SIDEBAR_TOOLS: tuple[SidebarTool, ...] = (
    SidebarTool('Central de Comandos BLING', 'Diagnóstico e correção', _render_bling_command_center_lazy),
    SidebarTool('Ferramentas de conferência', 'Diagnóstico e correção', _render_diagnostics_panel_lazy),
    SidebarTool('Assistente IA de correção', 'Diagnóstico e correção', _render_ai_maintenance_panel_lazy),
    SidebarTool('Manutenção do sistema', 'Sistema e manutenção', _render_maintenance_panel_lazy),
    SidebarTool('Módulos e recursos', 'Recursos disponíveis', _render_features_panel_lazy),
)

SIDEBAR_GROUPS: tuple[tuple[str, str], ...] = (
    ('Diagnóstico e correção', 'Comandos BLING, varreduras, simulações e assistência técnica.'),
    ('Sistema e manutenção', 'Logs, auditoria, limpeza e suporte operacional.'),
    ('Recursos disponíveis', 'Lista de módulos e capacidades carregadas no sistema.'),
)


def _render_sidebar_header() -> None:
    with st.sidebar:
        st.markdown(
            """
            <section class="bling-sidebar-hero" aria-label="Ferramentas do sistema">
                <div class="bling-sidebar-kicker">Painel de apoio</div>
                <div class="bling-sidebar-title">Central técnica</div>
                <div class="bling-sidebar-text">Diagnóstico, comandos BLING, logs e manutenção. As entradas reais continuam no fluxo principal.</div>
            </section>
            """,
            unsafe_allow_html=True,
        )


def _render_sidebar_group_header(title: str, caption: str) -> None:
    with st.sidebar:
        st.markdown(
            f"""
            <div class="bling-sidebar-group" aria-label="{title}">
                <div class="bling-sidebar-group-title">{title}</div>
                <div class="bling-sidebar-group-caption">{caption}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _render_sidebar_tool(name: str, renderer: SidebarRenderer) -> None:
    """Executa uma ferramenta da sidebar sem deixar uma falha derrubar o app."""
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


def _clear_legacy_sidebar_rules_state() -> None:
    legacy_keys = [
        'sidebar_rules_center_requested',
        'sidebar_open_rules_center_inline',
    ]
    removed: list[str] = []
    for key in legacy_keys:
        if key in st.session_state:
            removed.append(key)
            st.session_state.pop(key, None)
    if removed:
        add_audit_event(
            'legacy_sidebar_rules_state_cleared',
            area='SIDEBAR',
            details={'removed_keys': removed, 'responsible_file': 'bling_app_zero/ui/sidebar_tools.py'},
        )


def _tools_for_group(group: str) -> list[SidebarTool]:
    return [tool for tool in SIDEBAR_TOOLS if tool.group == group]


def render_sidebar_tools() -> None:
    inject_sidebar_tools_theme()
    _ensure_sidebar_defaults()
    _clear_legacy_sidebar_rules_state()
    _render_sidebar_header()

    add_audit_event(
        'sidebar_tools_rendered',
        area='SIDEBAR',
        details={
            'mode': 'grouped_sidebar_with_safe_lazy_imports',
            'groups': [group for group, _ in SIDEBAR_GROUPS],
            'tools': [tool.name for tool in SIDEBAR_TOOLS],
            'rules_location': 'main_flow_only',
            'audit_location': 'maintenance_panel',
            'command_center_location': 'sidebar_group_diagnostics',
            'guided_login_location': 'site_origin_module',
            'responsible_file': 'bling_app_zero/ui/sidebar_tools.py',
        },
    )

    for group, caption in SIDEBAR_GROUPS:
        tools = _tools_for_group(group)
        if not tools:
            continue
        _render_sidebar_group_header(group, caption)
        for tool in tools:
            _render_sidebar_tool(tool.name, tool.renderer)


__all__ = ['render_sidebar_tools']
