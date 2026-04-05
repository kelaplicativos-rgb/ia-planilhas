import traceback

import streamlit as st

APP_VERSION = "1.0.4"

from bling_app_zero.ui.state import init_state
from bling_app_zero.ui import origem_dados as origem_dados_ui
from bling_app_zero.ui.bling_panel import (
    render_bling_import_panel,
    render_bling_panel,
)

st.set_page_config(
    page_title="Bling Manual PRO",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def log(msg):
    if "logs" not in st.session_state:
        st.session_state["logs"] = []
    st.session_state["logs"].append(str(msg))


def aplicar_estilo_global() -> None:
    st.markdown(
        """
        <style>
        .block-container{
            padding-top: 0.8rem;
            padding-bottom: 1rem;
            padding-left: 0.7rem;
            padding-right: 0.7rem;
            max-width: 1400px;
        }
        [data-testid="stHeader"]{
            height:0;
        }
        [data-testid="stToolbar"]{
            right: 0.4rem;
            top: 0.2rem;
        }
        .stButton > button,
        .stDownloadButton > button{
            border-radius: 10px !important;
            min-height: 42px !important;
            font-weight: 600 !important;
        }
        .stMetric{
            border: 1px solid rgba(128,128,128,.18);
            border-radius: 12px;
            padding: .35rem .6rem;
        }
        @media (max-width: 768px){
            .block-container{
                padding-top: 0.45rem;
                padding-left: 0.45rem;
                padding-right: 0.45rem;
                padding-bottom: 0.8rem;
            }
            .stButton > button,
            .stDownloadButton > button{
                width: 100%;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def main():
    aplicar_estilo_global()
    init_state()

    try:
        origem_dados_ui.render_origem_dados()
    except Exception as e:
        st.error(f"Erro na tela Origem dos dados: {e}")
        log(f"Erro Origem dos dados: {traceback.format_exc()}")

    try:
        render_bling_panel()
    except Exception as e:
        st.error(f"Erro no painel Bling: {e}")
        log(f"Erro Painel Bling: {traceback.format_exc()}")

    try:
        render_bling_import_panel()
    except Exception as e:
        st.error(f"Erro na importação Bling: {e}")
        log(f"Erro Importação Bling: {traceback.format_exc()}")


if __name__ == "__main__":
    main()
