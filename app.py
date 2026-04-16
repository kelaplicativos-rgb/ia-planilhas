import streamlit as st
from bling_app_zero.utils.init_app import init_app
from bling_app_zero.ui.origem_dados import render_origem_dados

init_app()

st.set_page_config(
    page_title="IA Planilhas → Bling",
    layout="wide"
)

st.title("🚀 IA Planilhas → Bling")

# Controle de etapa
if "etapa" not in st.session_state:
    st.session_state["etapa"] = "origem"

# Roteamento simples
if st.session_state["etapa"] == "origem":
    render_origem_dados()
