import traceback

import streamlit as st

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

        @media (max-width: 768px){
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


def _obter_render_origem_dados():
    if hasattr(origem_dados_ui, "render_origem_dados"):
        return origem_dados_ui.render_origem_dados

    if hasattr(origem_dados_ui, "tela_origem_dados"):
        return origem_dados_ui.tela_origem_dados

    nomes_disponiveis = [nome for nome in dir(origem_dados_ui) if not nome.startswith("_")]
    raise AttributeError(
        "O módulo 'bling_app_zero.ui.origem_dados' não possui "
        "'render_origem_dados' nem 'tela_origem_dados'. "
        f"Nomes encontrados: {nomes_disponiveis}"
    )


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


def main() -> None:
    init_state()
    aplicar_estilo_global()

    st.title("Bling Manual PRO")

    aba1, aba2 = st.tabs(
        [
            "Origem dos dados",
            "Integração Bling",
        ]
    )

    render_origem = _obter_render_origem_dados()

    with aba1:
        executar_seguro(render_origem, "Origem dos dados")

    with aba2:
        executar_seguro(render_bling_panel, "Painel Bling")
        st.divider()
        executar_seguro(render_bling_import_panel, "Importação Bling")

    st.divider()

    with st.expander("Logs do sistema"):
        logs = st.session_state.get("logs", [])
        if logs:
            st.text_area("Logs", "\n".join(logs), height=200)
        else:
            st.write("Sem logs ainda.")


if __name__ == "__main__":
    main()
