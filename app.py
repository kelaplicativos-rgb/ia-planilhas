import streamlit as st
import traceback

from bling_app_zero.ui.state import init_state
from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.bling_panel import (
    render_bling_panel,
    render_bling_import_panel,
)
from bling_app_zero.ui.precificacao_panel import render_precificacao_panel
from bling_app_zero.ui.envio_panel import render_send_panel


# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="Bling Manual PRO",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# =========================
# LOG GLOBAL
# =========================
def log(msg):
    if "logs" not in st.session_state:
        st.session_state["logs"] = []

    st.session_state["logs"].append(str(msg))


# =========================
# ESTILO
# =========================
def aplicar_estilo_global() -> None:
    st.markdown(
        """
        <style>
        .block-container{
            padding-top: 0.8rem;
            padding-bottom: 1rem;
            padding-left: 0.7rem;
            padding-right: 0.7rem;
            max-width: 100%;
        }

        h1, h2, h3{
            margin-top: 0.2rem !important;
            margin-bottom: 0.6rem !important;
        }

        div.stButton > button,
        div.stDownloadButton > button {
            width: 100%;
            min-height: 42px;
            height: 42px;
            border-radius: 10px;
            font-size: 0.95rem;
            font-weight: 600;
            padding: 0 0.8rem;
        }

        div[data-testid="stNumberInput"] input,
        div[data-testid="stTextInput"] input,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        div[data-testid="stTextArea"] textarea {
            min-height: 40px;
        }

        div[data-testid="stTabs"] button {
            border-radius: 10px;
            min-height: 40px;
            font-weight: 600;
        }

        details {
            border-radius: 10px;
        }

        div[data-testid="stDataFrame"],
        div[data-testid="stDataEditor"] {
            border-radius: 10px;
            overflow: hidden;
        }

        @media (max-width: 768px) {
            .block-container{
                padding-top: 0.55rem;
                padding-bottom: 0.8rem;
                padding-left: 0.45rem;
                padding-right: 0.45rem;
            }

            h1{ font-size: 1.35rem !important; }
            h2{ font-size: 1.10rem !important; }
            h3{ font-size: 1rem !important; }

            div.stButton > button,
            div.stDownloadButton > button {
                min-height: 38px;
                height: 38px;
                font-size: 0.88rem;
                border-radius: 9px;
            }

            div[data-testid="stTabs"] button {
                min-height: 38px;
                font-size: 0.82rem;
            }

            p, label, .stCaption {
                font-size: 0.86rem !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================
# EXECUTOR SEGURO
# =========================
def executar_seguro(func, nome):
    try:
        func()
    except Exception as e:
        erro = f"Erro em {nome}: {e}"
        log(erro)
        log(traceback.format_exc())

        st.error(f"❌ {erro}")
        with st.expander("Detalhes do erro"):
            st.code(traceback.format_exc())


# =========================
# MAIN
# =========================
def main() -> None:
    init_state()
    aplicar_estilo_global()

    st.title("Bling Manual PRO")

    aba1, aba2, aba3, aba4 = st.tabs(
        [
            "Origem dos dados",
            "Integração Bling",
            "Precificação",
            "Envio",
        ]
    )

    # =========================
    # ABAS COM PROTEÇÃO
    # =========================

    with aba1:
        executar_seguro(render_origem_dados, "Origem dos dados")

    with aba2:
        executar_seguro(render_bling_panel, "Painel Bling")
        st.divider()
        executar_seguro(render_bling_import_panel, "Importação Bling")

    with aba3:
        executar_seguro(render_precificacao_panel, "Precificação")

    with aba4:
        executar_seguro(render_send_panel, "Envio")

    # =========================
    # LOGS VISÍVEIS
    # =========================
    st.divider()

    with st.expander("📄 Logs do sistema"):
        logs = st.session_state.get("logs", [])
        if logs:
            st.text_area("Logs", "\n".join(logs), height=200)
        else:
            st.write("Sem logs ainda.")


# =========================
# START
# =========================
if __name__ == "__main__":
    main()
