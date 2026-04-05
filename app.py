import streamlit as st
import traceback

from bling_app_zero.ui.state import init_state
from bling_app_zero.ui import origem_dados as origem_dados_ui
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
        """,
        unsafe_allow_html=True,
    )


# =========================
# RESOLUÇÃO SEGURA DE ORIGEM
# =========================
def _obter_render_origem_dados():
    """
    Evita quebrar a aplicação caso o módulo de origem esteja exportando
    'tela_origem_dados' em vez de 'render_origem_dados' em algum deploy
    intermediário ou cache antigo do ambiente.
    """
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

    render_origem = _obter_render_origem_dados()

    # =========================
    # ABAS COM PROTEÇÃO
    # =========================
    with aba1:
        executar_seguro(render_origem, "Origem dos dados")

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
    with st.expander(" Logs do sistema"):
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
