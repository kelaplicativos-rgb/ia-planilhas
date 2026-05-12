from __future__ import annotations

import traceback

import streamlit as st

from bling_app_zero.core.debug import add_debug
from bling_app_zero.ui.home import render_home
from bling_app_zero.ui.sidebar_tools import render_sidebar_tools


APP_VERSION = '3.5.23-BLINGFIX-CLEAN-ALERTS'


def _inject_streamlit_toolbar_fix() -> None:
    """Mantem visiveis menu superior, tres pontinhos e controle da sidebar."""
    st.markdown(
        """
        <style>
        header[data-testid="stHeader"],
        header[data-testid="stHeader"] *,
        div[data-testid="stToolbar"],
        div[data-testid="stToolbar"] *,
        div[data-testid="stDecoration"],
        div[data-testid="stStatusWidget"],
        #MainMenu,
        section[data-testid="stSidebar"],
        section[data-testid="stSidebar"] * {
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
        }

        header[data-testid="stHeader"] {
            display: block !important;
            z-index: 999999 !important;
            overflow: visible !important;
        }

        #MainMenu {
            display: block !important;
        }

        section[data-testid="stSidebar"] {
            z-index: 1000002 !important;
            overflow: visible !important;
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
        render_sidebar_tools()
    except Exception as exc:
        formatted = _register_critical_error(exc)
        st.error('Encontrei um erro interno, mas o aplicativo continuou aberto.')
        st.caption('Abra a barra lateral, baixe o log debug e envie para o próximo BLINGFIX.')
        with st.expander('Ver detalhe técnico do erro', expanded=False):
            st.code(formatted)


if __name__ == '__main__':
    main()
