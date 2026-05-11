from __future__ import annotations

import traceback

import streamlit as st

from bling_app_zero.core.debug import add_debug
from bling_app_zero.ui.home import render_home
from bling_app_zero.ui.sidebar_tools import render_sidebar_tools


APP_VERSION = '3.5.10-BLINGFIX-SIDEBAR-RECURSOS'


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

        /* BLINGFIX: deixa o progresso do wizard e a trilha de etapas dentro do padrão visual de cards. */
        div[data-testid="stProgress"] {
            width: min(100%, 760px) !important;
            margin: 0 auto 0.55rem auto !important;
            padding: 1rem 1rem 0.95rem 1rem !important;
            border: 1px solid rgba(37, 99, 235, 0.14) !important;
            border-radius: 24px !important;
            background: linear-gradient(135deg, rgba(255,255,255,0.98), rgba(241,247,255,0.94)) !important;
            box-shadow: 0 16px 42px rgba(15, 23, 42, 0.065) !important;
            position: relative !important;
            overflow: hidden !important;
            box-sizing: border-box !important;
        }

        div[data-testid="stProgress"]::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, #2563eb, #38bdf8);
        }

        div[data-testid="stProgress"] > div {
            margin: 0 !important;
        }

        div[data-testid="stProgress"] div[role="progressbar"] {
            border-radius: 999px !important;
            overflow: hidden !important;
        }

        div[data-testid="stProgress"] p {
            color: #64748b !important;
            font-weight: 720 !important;
            line-height: 1.35 !important;
        }

        div[data-testid="stCaptionContainer"] {
            width: min(100%, 760px) !important;
            margin: -0.2rem auto 1rem auto !important;
            padding: 0.72rem 0.88rem !important;
            border: 1px solid rgba(37, 99, 235, 0.12) !important;
            border-radius: 18px !important;
            background: rgba(239, 246, 255, 0.88) !important;
            box-shadow: 0 8px 22px rgba(15, 23, 42, 0.045) !important;
            box-sizing: border-box !important;
        }

        div[data-testid="stCaptionContainer"] p {
            margin: 0 !important;
            color: #64748b !important;
            font-size: 0.86rem !important;
            line-height: 1.42 !important;
            font-weight: 650 !important;
        }

        @media (max-width: 760px) {
            div[data-testid="stProgress"],
            div[data-testid="stCaptionContainer"] {
                width: 100% !important;
                margin-left: 0 !important;
                margin-right: 0 !important;
                border-radius: 20px !important;
            }

            div[data-testid="stProgress"] {
                padding: 0.9rem 0.85rem 0.85rem 0.85rem !important;
            }

            div[data-testid="stCaptionContainer"] {
                padding: 0.62rem 0.72rem !important;
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
