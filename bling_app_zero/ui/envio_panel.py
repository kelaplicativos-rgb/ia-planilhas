import traceback
import streamlit as st

APP_VERSION = "1.0.13"


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
        """,
        unsafe_allow_html=True,
    )


def main():
    from bling_app_zero.ui.state import init_state
    from bling_app_zero.ui.bling_panel import (
        render_bling_import_panel,
        render_bling_panel,
    )
    from bling_app_zero.ui.envio_panel import render_send_panel

    aplicar_estilo_global()
    init_state()

    # 🔥 ORDEM CORRETA DO SISTEMA
    tab1, tab2, tab3 = st.tabs(
        ["Origem dos dados", "Integração Bling", "Envio por API"]
    )

    # =========================
    # ORIGEM DOS DADOS (CORE)
    # =========================
    with tab1:
        try:
            from bling_app_zero.ui import origem_dados as origem_dados_ui

            origem_dados_ui.render_origem_dados()
        except Exception as e:
            st.error(f"Erro na tela Origem dos dados: {e}")
            log(f"Erro Origem dos dados: {traceback.format_exc()}")

    # =========================
    # BLING (CONEXÃO)
    # =========================
    with tab2:
        try:
            render_bling_panel()
            st.markdown("---")
            render_bling_import_panel()
        except Exception as e:
            st.error(f"Erro no painel Bling: {e}")
            log(f"Erro Painel Bling: {traceback.format_exc()}")

    # =========================
    # ENVIO (ISOLADO)
    # =========================
    with tab3:
        try:
            # 🔒 PROTEÇÃO: só permite envio se existir DF final
            if "df_final" not in st.session_state or st.session_state["df_final"] is None:
                st.warning("Gere a planilha primeiro na aba Origem dos dados")
            else:
                render_send_panel()
        except Exception as e:
            st.error(f"Erro na aba Envio por API: {e}")
            log(f"Erro Envio por API: {traceback.format_exc()}")

    # =========================
    # RODAPÉ
    # =========================
    with st.sidebar:
        st.caption(f"Versão {APP_VERSION}")


if __name__ == "__main__":
    main()
