from __future__ import annotations

import traceback
from collections.abc import Callable
from dataclasses import dataclass

import streamlit as st
import streamlit.components.v1 as components

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.debug import add_debug
from bling_app_zero.production.production_config import admin_mode_enabled

SidebarRenderer = Callable[[], None]
SIDEBAR_CLEAN_DONE_KEY = 'sidebar_legacy_noise_clean_done'
BLING_OAUTH_GUARD_KEY = 'bling_oauth_top_navigation_guard_injected'


@dataclass(frozen=True)
class SidebarTool:
    name: str
    renderer: SidebarRenderer
    admin_only: bool = False


def _render_production_sidebar_lazy() -> None:
    from bling_app_zero.ui.production_sidebar import render_production_sidebar

    render_production_sidebar()


def _render_flow_simulator_panel_lazy() -> None:
    from bling_app_zero.ui.flow_simulator_panel import render_flow_simulator_panel

    render_flow_simulator_panel()


def _render_rota_cheia_panel_lazy() -> None:
    from bling_app_zero.ui.rota_cheia_panel import render_rota_cheia_panel

    render_rota_cheia_panel()


def _render_credits_sidebar_lazy() -> None:
    from bling_app_zero.ui.credits_sidebar import render_credits_sidebar

    render_credits_sidebar()


SIDEBAR_TOOLS: tuple[SidebarTool, ...] = (
    SidebarTool('Produção MapeiaAI', _render_production_sidebar_lazy, admin_only=False),
    SidebarTool('Verificar sistema', _render_flow_simulator_panel_lazy, admin_only=False),
    SidebarTool('SCAN BLA / Rota Cheia', _render_rota_cheia_panel_lazy, admin_only=False),
    SidebarTool('Créditos MapeiaAI', _render_credits_sidebar_lazy, admin_only=True),
)


def _inject_bling_oauth_top_navigation_guard() -> None:
    """Força o OAuth do Bling a abrir fora do iframe/webview do Streamlit."""
    if st.session_state.get(BLING_OAUTH_GUARD_KEY):
        return
    st.session_state[BLING_OAUTH_GUARD_KEY] = True
    components.html(
        """
<script>
(function () {
  function bindBlingOAuthLinks() {
    try {
      const doc = window.parent && window.parent.document ? window.parent.document : document;
      const links = doc.querySelectorAll('a[href*="bling.com.br/Api/v3/oauth/authorize"], a[href*="bling.com.br/api/v3/oauth/authorize"]');
      links.forEach(function (link) {
        if (link.dataset.blingTopBound === '1') return;
        link.dataset.blingTopBound = '1';
        link.setAttribute('target', '_top');
        link.setAttribute('rel', 'noopener noreferrer');
        link.addEventListener('click', function (event) {
          const href = link.getAttribute('href');
          if (!href) return;
          event.preventDefault();
          if (window.top) {
            window.top.location.href = href;
          } else {
            window.location.href = href;
          }
        }, true);
      });
    } catch (error) {
      // Fallback silencioso: o link HTML continua visível mesmo se o guard não conseguir acessar o parent.
    }
  }
  bindBlingOAuthLinks();
  let attempts = 0;
  const timer = window.setInterval(function () {
    attempts += 1;
    bindBlingOAuthLinks();
    if (attempts >= 10) window.clearInterval(timer);
  }, 350);
})();
</script>
""",
        height=0,
        width=0,
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
    _inject_bling_oauth_top_navigation_guard()
    _clear_legacy_sidebar_noise_state_once()
    for tool in SIDEBAR_TOOLS:
        _render_sidebar_tool(tool)


__all__ = ['render_sidebar_tools']
