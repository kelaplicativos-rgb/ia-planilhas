import traceback
import streamlit as st

APP_VERSION = "1.0.20"

from bling_app_zero.ui.state import init_state
from bling_app_zero.ui import origem_dados as origem_dados_ui
from bling_app_zero.ui.bling_panel import (
    render_bling_panel,
    render_bling_import_panel,
)
from bling_app_zero.ui.envio_panel import render_send_panel


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

    # 🔥 FLUXO CORRETO
    tab1, tab2, tab3 = st.tabs(
        [
            "Origem dos dados",
            "Integração Bling",
            "Envio por API",
        ]
    )

    # =========================
    # ORIGEM DOS DADOS (CORE)
    # =========================
    with tab1:
        executar_seguro(
            origem_dados_ui.render_origem_dados,
            "Origem dos dados",
        )

    # =========================
    # BLING (LOGIN + IMPORT)
    # =========================
    with tab2:
        executar_seguro(render_bling_panel, "Painel Bling")
        st.markdown("---")
        executar_seguro(render_bling_import_panel, "Importação Bling")

    # =========================
    # ENVIO (ISOLADO)
    # =========================
    with tab3:
        try:
            if "df_final" not in st.session_state or st.session_state["df_final"] is None:
                st.warning("Gere a planilha primeiro na aba Origem dos dados")
            else:
                executar_seguro(render_send_panel, "Envio por API")
        except Exception as e:
            st.error(f"Erro no envio: {e}")
            log(traceback.format_exc())

    # =========================
    # RODAPÉ
    # =========================
    with st.sidebar:
        st.caption(f"Versão {APP_VERSION}")


if __name__ == "__main__":
    main()
