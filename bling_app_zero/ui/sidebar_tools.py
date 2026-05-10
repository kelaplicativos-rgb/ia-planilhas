from __future__ import annotations

import traceback
from collections.abc import Callable

import streamlit as st

from bling_app_zero.core.debug import add_debug, render_debug_panel
from bling_app_zero.ui.diagnostics_panel import render_diagnostics_panel
from bling_app_zero.ui.layout.sidebar_theme import inject_sidebar_tools_theme
from bling_app_zero.ui.rules_panel import render_rules_panel


SidebarRenderer = Callable[[], None]


SIDEBAR_TOOLS: tuple[tuple[str, SidebarRenderer], ...] = (
    ('Ferramentas de conferência', render_diagnostics_panel),
    ('Logs técnicos', render_debug_panel),
    ('Regras e recursos do CSV final', render_rules_panel),
)


def _render_sidebar_header() -> None:
    with st.sidebar:
        st.markdown(
            """
            <section class="bling-sidebar-hero" aria-label="Ferramentas do sistema">
                <div class="bling-sidebar-kicker">Painel técnico</div>
                <div class="bling-sidebar-title">Ferramentas do sistema</div>
                <div class="bling-sidebar-text">Conferência, logs e regras do CSV em módulos separados.</div>
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
        with st.sidebar:
            with st.expander(f'{name} indisponível', expanded=True):
                st.error(f'O módulo {name} falhou, mas os outros recursos continuam disponíveis.')
                st.caption('Baixe o log técnico e envie para o próximo BLINGFIX.')


def render_sidebar_tools() -> None:
    """Renderiza a sidebar técnica mantendo cada ferramenta em seu próprio módulo.

    A responsabilidade deste arquivo é só orquestrar. O conteúdo de cada ferramenta
    continua isolado nos módulos próprios:
    - diagnostics_panel.py
    - core/debug.py
    - rules_panel.py
    """
    inject_sidebar_tools_theme()
    _render_sidebar_header()
    for name, renderer in SIDEBAR_TOOLS:
        _render_sidebar_tool(name, renderer)


__all__ = ['render_sidebar_tools']
