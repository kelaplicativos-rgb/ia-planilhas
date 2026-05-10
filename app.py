from __future__ import annotations

import traceback
from collections.abc import Callable

import streamlit as st

from bling_app_zero.core.debug import add_debug
from bling_app_zero.ui.home import render_home


APP_VERSION = '3.5.8-SIDEBAR-HUB'


def _inject_streamlit_toolbar_fix() -> None:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] {
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
            z-index: 999998 !important;
        }
        header[data-testid="stHeader"] {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
            z-index: 999999 !important;
        }
        #MainMenu, div[data-testid="stToolbar"] {
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
            z-index: 1000000 !important;
        }
        button[kind="header"], button[data-testid="collapsedControl"], [data-testid="collapsedControl"] {
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _register_critical_error(exc: Exception) -> str:
    formatted = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    add_debug(f'Falha critica: {exc}', origin='APP', level='ERRO')
    add_debug(formatted, origin='TRACEBACK', level='ERRO')
    return formatted


def _render_sidebar_block(name: str, renderer: Callable[[], None]) -> None:
    try:
        renderer()
    except Exception as exc:
        formatted = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        add_debug(f'Falha no bloco da sidebar {name}: {exc}', origin='SIDEBAR', level='ERRO')
        add_debug(formatted, origin='TRACEBACK', level='ERRO')
        with st.sidebar:
            st.error(f'O bloco {name} falhou, mas o painel continua disponível.')
            st.caption('Abra Logs técnicos e baixe o debug.')


def _render_sidebar_tools() -> None:
    from bling_app_zero.core.debug import render_debug_panel
    from bling_app_zero.ui.diagnostics_panel import render_diagnostics_panel
    from bling_app_zero.ui.rules_panel import render_rules_panel

    with st.sidebar:
        st.markdown('### Painel lateral')
        st.caption('Escolha uma área. No celular isso evita que um bloco esconda os outros.')
        section = st.radio(
            'Área da sidebar',
            ['Ferramentas', 'Logs', 'Regras'],
            horizontal=True,
            key='sidebar_hub_area',
            label_visibility='collapsed',
        )
        st.divider()

    if section == 'Logs':
        _render_sidebar_block('Logs técnicos', render_debug_panel)
    elif section == 'Regras':
        _render_sidebar_block('Regras e recursos do CSV final', render_rules_panel)
    else:
        _render_sidebar_block('Ferramentas de conferência', render_diagnostics_panel)


def main() -> None:
    st.set_page_config(
        page_title='IA Planilhas → Bling',
        page_icon='🚀',
        layout='wide',
        initial_sidebar_state='collapsed',
    )
    _inject_streamlit_toolbar_fix()

    add_debug(f'Aplicacao iniciada | versao {APP_VERSION}', origin='APP')

    try:
        render_home()
        _render_sidebar_tools()
    except Exception as exc:
        formatted = _register_critical_error(exc)
        st.error('Encontrei um erro interno, mas o aplicativo continuou aberto.')
        st.caption('Abra a barra lateral, baixe o log debug e envie para o próximo BLINGFIX.')
        with st.expander('Ver detalhe técnico do erro', expanded=False):
            st.code(formatted)


if __name__ == '__main__':
    main()
