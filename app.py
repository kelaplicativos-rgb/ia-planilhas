from __future__ import annotations

import traceback

import streamlit as st

from bling_app_zero.core.debug import add_debug
from bling_app_zero.ui.home import render_home
from bling_app_zero.ui.sidebar_tools import render_sidebar_tools


APP_VERSION = '3.5.19-BLINGCLEAN-MAPPING-PAGINADO'


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
            z-index: 1000002 !important;
            overflow: visible !important;
        }

        section[data-testid="stSidebar"] * {
            pointer-events: auto !important;
        }

        section[data-testid="stSidebar"] button,
        section[data-testid="stSidebar"] button[kind="header"],
        section[data-testid="stSidebar"] button[data-testid="baseButton-header"],
        section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"],
        section[data-testid="stSidebar"] [data-testid="collapsedControl"],
        button[kind="header"],
        button[data-testid="collapsedControl"],
        button[data-testid="baseButton-header"],
        [data-testid="collapsedControl"],
        [data-testid="stSidebarCollapseButton"],
        button[aria-label*="sidebar" i],
        button[title*="sidebar" i] {
            display: flex !important;
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
            z-index: 1000005 !important;
        }

        section[data-testid="stSidebar"] button[kind="header"],
        section[data-testid="stSidebar"] button[data-testid="baseButton-header"],
        section[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"],
        section[data-testid="stSidebar"] button[aria-label*="sidebar" i],
        section[data-testid="stSidebar"] button[title*="sidebar" i] {
            position: sticky !important;
            top: 0.45rem !important;
            margin-left: auto !important;
            margin-right: 0.35rem !important;
            width: 2.25rem !important;
            min-width: 2.25rem !important;
            height: 2.25rem !important;
            min-height: 2.25rem !important;
            align-items: center !important;
            justify-content: center !important;
            border-radius: 999px !important;
            background: rgba(255, 255, 255, 0.96) !important;
            border: 1px solid rgba(37, 99, 235, 0.18) !important;
            box-shadow: 0 8px 18px rgba(15, 23, 42, 0.10) !important;
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

        .bling-model-step-card {
            margin-bottom: 0 !important;
            border-bottom-left-radius: 0 !important;
            border-bottom-right-radius: 0 !important;
            border-bottom: 0 !important;
            box-shadow: 0 8px 24px rgba(15, 23, 42, 0.045) !important;
        }

        .bling-model-upload-anchor {
            height: 0.35rem !important;
        }

        .bling-model-step-card + div[data-testid="stFileUploader"],
        .bling-model-step-card ~ div[data-testid="stFileUploader"]:first-of-type {
            width: min(100%, 760px) !important;
            margin: 0 auto 1rem auto !important;
            padding: 0 1.15rem 1.15rem 1.15rem !important;
            border: 1px solid rgba(37, 99, 235, 0.14) !important;
            border-top: 0 !important;
            border-bottom-left-radius: 24px !important;
            border-bottom-right-radius: 24px !important;
            background: linear-gradient(135deg, rgba(255,255,255,0.98), rgba(241,247,255,0.94)) !important;
            box-shadow: 0 16px 42px rgba(15, 23, 42, 0.065) !important;
            box-sizing: border-box !important;
        }

        .bling-model-step-card + div[data-testid="stFileUploader"] section,
        .bling-model-step-card ~ div[data-testid="stFileUploader"]:first-of-type section {
            margin-top: 0 !important;
            border-radius: 18px !important;
            background: rgba(255,255,255,0.82) !important;
        }

        @media (max-width: 760px) {
            .bling-wizard-progress-card {
                padding: 0.9rem 0.85rem 0.85rem 0.85rem !important;
            }

            .bling-wizard-progress-title,
            .bling-wizard-steps-line {
                font-size: 0.78rem !important;
            }

            .bling-model-step-card + div[data-testid="stFileUploader"],
            .bling-model-step-card ~ div[data-testid="stFileUploader"]:first-of-type {
                width: 100% !important;
                margin-left: 0 !important;
                margin-right: 0 !important;
                padding: 0 0.92rem 0.92rem 0.92rem !important;
                border-bottom-left-radius: 20px !important;
                border-bottom-right-radius: 20px !important;
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
