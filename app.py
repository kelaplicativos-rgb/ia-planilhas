
import streamlit as st

from bling_app_zero.utils.init_app import init_app
from bling_app_zero.ui.app_helpers import get_etapa
from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.origem_precificacao import render_origem_precificacao
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.ui.preview_final import render_preview_final

st.set_page_config(page_title="IA Planilhas → Bling", layout="wide")

init_app()

if "operacao" not in st.session_state:
    st.session_state["operacao"] = "cadastro"

st.sidebar.title("IA Planilhas → Bling")
st.sidebar.radio(
    "Operação",
    options=["cadastro", "estoque"],
    key="operacao",
    format_func=lambda x: "Cadastro de Produtos" if x == "cadastro" else "Atualização de Estoque",
)

etapa = get_etapa()

if etapa == "origem":
    render_origem_dados()
elif etapa == "precificacao":
    render_origem_precificacao()
elif etapa == "mapeamento":
    render_origem_mapeamento()
elif etapa == "final":
    render_preview_final()
else:
    st.session_state["etapa"] = "origem"
    st.rerun()
