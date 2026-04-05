import traceback

import streamlit as st

APP_VERSION = "1.0.5"

from bling_app_zero.ui.state import init_state
from bling_app_zero.ui import origem_dados as origem_dados_ui
from bling_app_zero.ui.bling_panel import (
    render_bling_import_panel,
    render_bling_panel,
)
from bling_app_zero.ui.precificacao_panel import render_precificacao_panel
from bling_app_zero.ui.envio_panel import render_send_panel


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
        .stTabs [data-baseweb="tab-list"]{
            gap: 0.35rem;
            flex-wrap: wrap;
        }
        .stTabs [data-baseweb="tab"]{
            height: auto;
            white-space: nowrap;
            padding: 0.55rem 0.9rem;
            border-radius: 0.7rem;
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


def executar_seguro(func, nome: str) -> None:
    try:
        func()
    except Exception as e:
        erro = f"Erro em {nome}: {e}"
        log(erro)
        log(traceback.format_exc())
        st.error(f"❌ {erro}")
        with st.expander("Detalhes do erro"):
            st.code(traceback.format_exc())


def main() -> None:
    aplicar_estilo_global()
    init_state()

    st.title("Bling Manual PRO")
    st.caption(f"Versão {APP_VERSION}")

    aba1, aba2, aba3, aba4 = st.tabs(
        [
            "Origem dos dados",
            "Integração Bling",
            "Precificação",
            "Envio",
        ]
    )

    with aba1:
        executar_seguro(origem_dados_ui.render_origem_dados, "Origem dos dados")

    with aba2:
        executar_seguro(render_bling_panel, "Painel Bling")
        st.divider()
        executar_seguro(render_bling_import_panel, "Importação Bling")

    with aba3:
        executar_seguro(render_precificacao_panel, "Precificação")

    with aba4:
        executar_seguro(render_send_panel, "Envio")

    logs = st.session_state.get("logs", [])
    if logs:
        st.divider()
        with st.expander("Logs do sistema"):
            st.text_area("Logs", "\n".join(logs), height=200)


if __name__ == "__main__":
    main()
