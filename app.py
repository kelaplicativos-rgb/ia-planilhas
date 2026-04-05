import traceback

import streamlit as st

from bling_app_zero.ui.state import init_state
from bling_app_zero.ui.origem_dados import tela_origem_dados
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
def log(msg: str) -> None:
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

        div[data-testid="stTabs"] button {
            min-height: 42px;
        }

        @media (max-width: 768px) {
            .block-container{
                padding-top: 0.5rem;
                padding-left: 0.45rem;
                padding-right: 0.45rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# =========================
# EXECUTOR SEGURO
# =========================
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

    with aba1:
        executar_seguro(tela_origem_dados, "Origem dos dados")

    with aba2:
        executar_seguro(render_bling_panel, "Painel Bling")
        st.divider()
        executar_seguro(render_bling_import_panel, "Importação Bling")

    with aba3:
        executar_seguro(render_precificacao_panel, "Precificação")

    with aba4:
        executar_seguro(render_send_panel, "Envio")

    st.divider()

    with st.expander("Logs do sistema"):
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
