import traceback

import streamlit as st

APP_VERSION = "1.0.11"

from bling_app_zero.ui.state import init_state
from bling_app_zero.ui import origem_dados as origem_dados_ui


st.set_page_config(
    page_title="Bling Manual PRO",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def log(msg) -> None:
    try:
        if "logs" not in st.session_state:
            st.session_state["logs"] = []
        st.session_state["logs"].append(str(msg))
    except Exception:
        pass


def aplicar_estilo_global() -> None:
    st.markdown(
        """
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    aplicar_estilo_global()
    init_state()

    try:
        origem_dados_ui.render_origem_dados()
    except Exception as e:
        st.error(f"Erro na tela Origem dos dados: {e}")
        log(f"Erro Origem dos dados: {traceback.format_exc()}")

    with st.sidebar:
        st.caption(f"Versão {APP_VERSION}")


if __name__ == "__main__":
    main()
