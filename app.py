from __future__ import annotations

import traceback

import streamlit as st

from bling_app_zero.core.debug import add_debug
from bling_app_zero.ui.home import render_home
from bling_app_zero.ui.sidebar_tools import render_sidebar_tools


APP_VERSION = '3.5.12-BLINGFIX-RECURSOS-PADRAO-SIM'


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

        .bling-wizard-progress-card {
            padding: 1rem 1rem 0.95rem 1rem !important;
            margin-bottom: 1rem !important;
        }

        .bling-wizard-progress-title {
            color: #64748b !important;
            font-size: 0.86rem !important;
            font-weight: 820 !important;
            line-height: 1.35 !important;
            margin: 0 0 0.55rem 0 !important;
        }

        .bling-wizard-progress-track {
            width: 100% !important;
            height: 0.48rem !important;
            border-radius: 999px !important;
            background: rgba(226, 232, 240, 0.82) !important;
            overflow: hidden !important;
            margin: 0 0 0.86rem 0 !important;
        }

        .bling-wizard-progress-fill {
            height: 100% !important;
            border-radius: 999px !important;
            background: linear-gradient(90deg, #2563eb, #38bdf8) !important;
        }

        .bling-wizard-steps-line {
            color: #64748b !important;
            font-size: 0.86rem !important;
            font-weight: 720 !important;
            line-height: 1.42 !important;
            white-space: normal !important;
        }

        @media (max-width: 760px) {
            .bling-wizard-progress-card {
                padding: 0.9rem 0.85rem 0.85rem 0.85rem !important;
            }

            .bling-wizard-progress-title,
            .bling-wizard-steps-line {
                font-size: 0.78rem !important;
            }
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
