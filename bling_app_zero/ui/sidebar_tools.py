from __future__ import annotations

import traceback
from collections.abc import Callable
from dataclasses import dataclass

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.debug import add_debug
from bling_app_zero.production.production_config import admin_mode_enabled

SidebarRenderer = Callable[[], None]
SIDEBAR_CLEAN_DONE_KEY = 'sidebar_legacy_noise_clean_done'


@dataclass(frozen=True)
class SidebarTool:
    name: str
    renderer: SidebarRenderer
    admin_only: bool = False


def _render_production_sidebar_lazy() -> None:
    from bling_app_zero.ui.production_sidebar import render_production_sidebar

    render_production_sidebar()


def _render_credits_sidebar_lazy() -> None:
    from bling_app_zero.ui.credits_sidebar import render_credits_sidebar

    render_credits_sidebar()


def _render_support_diagnostic_panel_lazy() -> None:
    from bling_app_zero.ui.support_diagnostic_panel import render_support_diagnostic_panel

    render_support_diagnostic_panel()


SIDEBAR_TOOLS: tuple[SidebarTool, ...] = (
    SidebarTool('Produção MapeiaAI', _render_production_sidebar_lazy, admin_only=False),
    SidebarTool('Créditos MapeiaAI', _render_credits_sidebar_lazy, admin_only=True),
    SidebarTool('Enviar diagnóstico', _render_support_diagnostic_panel_lazy, admin_only=True),
)


def _render_sidebar_tool(tool: SidebarTool) -> None:
    if tool.admin_only and not admin_mode_enabled():
        return
    try:
        tool.renderer()
    except Exception as exc:
        formatted = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        add_debug(f'Falha no módulo da sidebar {tool.name}: {exc}', origin='SIDEBAR', level='ERRO')
        add_debug(formatted, origin='TRACEBACK', level='ERRO')
        add_audit_event(
            'sidebar_tool_failed',
            area='SIDEBAR',
            status='ERRO',
            details={'tool': tool.name, 'error': str(exc), 'responsible_file': 'bling_app_zero/ui/sidebar_tools.py'},
        )
        with st.sidebar:
            st.error(f'{tool.name} indisponível.')
            st.caption('Tire um print desta tela e envie no próximo BLINGFIX.')


def _clear_legacy_sidebar_noise_state_once() -> None:
    if st.session_state.get(SIDEBAR_CLEAN_DONE_KEY):
        return
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
    st.session_state[SIDEBAR_CLEAN_DONE_KEY] = True
    if removed:
        add_audit_event(
            'legacy_sidebar_noise_state_cleared',
            area='SIDEBAR',
            details={'removed_keys': removed, 'responsible_file': 'bling_app_zero/ui/sidebar_tools.py'},
        )


def render_sidebar_tools() -> None:
    _clear_legacy_sidebar_noise_state_once()
    for tool in SIDEBAR_TOOLS:
        _render_sidebar_tool(tool)


__all__ = ['render_sidebar_tools']
