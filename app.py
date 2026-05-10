from __future__ import annotations

import traceback
from collections.abc import Callable

import streamlit as st

from bling_app_zero.core.debug import add_debug
from bling_app_zero.ui.home import render_home


APP_VERSION = '3.5.7-BLINGFIX-SIDEBAR-ISOLADA'


def _inject_streamlit_toolbar_fix() -> None:
    """Mantem visiveis menu superior, tres pontinhos e controle da sidebar."""
    st.markdown(
        """
        <style>
        header[data-testid="stHeader"] {
            display: block !important;
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
            z-index: 999999 !important;
            overflow: visible !important;
        }

        header[data-testid="stHeader"] * {
            visibility: visible !important;
            pointer-events: auto !important;
        }

        div[data-testid="stToolbar"],
        div[data-testid="stToolbar"] *,
        div[data-testid="stDecoration"],
        div[data-testid="stStatusWidget"],
        #MainMenu {
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
            z-index: 1000000 !important;
        }

        #MainMenu {
            display: block !important;
        }

        section[data-testid="stSidebar"] {
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
            z-index: 999998 !important;
        }

        button[kind="header"],
        button[data-testid="collapsedControl"],
        [data-testid="collapsedControl"] {
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
            z-index: 1000001 !important;
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
    """Renderiza cada bloco da sidebar de forma isolada.

    Se Diagnóstico/BlingBrain quebrar, Logs técnicos e Regras continuam aparecendo.
    """
    try:
        renderer()
    except Exception as exc:
        formatted = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        add_debug(f'Falha no bloco da sidebar {name}: {exc}', origin='SIDEBAR', level='ERRO')
        add_debug(formatted, origin='TRACEBACK', level='ERRO')
        with st.sidebar:
            with st.expander(f'{name} indisponível', expanded=True):
                st.error(f'O bloco {name} falhou, mas os outros recursos continuam disponíveis.')
                st.caption('Baixe o log técnico e envie para o próximo BLINGFIX.')


def _render_sidebar_tools() -> None:
    from bling_app_zero.core.debug import render_debug_panel
    from bling_app_zero.ui.diagnostics_panel import render_diagnostics_panel
    from bling_app_zero.ui.rules_panel import render_rules_panel

    # Ferramentas sempre disponíveis na lateral.
    # Cada bloco é isolado para um erro não esconder os outros.
    _render_sidebar_block('Ferramentas de conferência', render_diagnostics_panel)
    _render_sidebar_block('Logs técnicos', render_debug_panel)
    _render_sidebar_block('Regras e recursos do CSV final', render_rules_panel)


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
