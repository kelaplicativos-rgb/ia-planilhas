
import streamlit as st

from bling_app_zero.utils.init_app import init_app
from bling_app_zero.ui.app_helpers import (
    get_etapa,
    render_topo_navegacao,
    sincronizar_etapa_da_url,
)
from bling_app_zero.ui.origem_dados import render_origem_dados

init_app()

st.set_page_config(
    page_title="IA Planilhas → Bling",
    layout="wide"
)

sincronizar_etapa_da_url()

st.title("🚀 IA Planilhas → Bling")
render_topo_navegacao()

etapa = get_etapa()

if etapa == "origem":
    render_origem_dados()

elif etapa == "precificacao":
    st.subheader("2. Precificação")
    st.info("Próxima etapa do rebuild: calculadora estilo Olist.")
    render_topo_navegacao()

elif etapa == "mapeamento":
    st.subheader("3. Mapeamento")
    st.info("Próxima etapa do rebuild: GPT fazendo o mapeamento.")
    render_topo_navegacao()

elif etapa == "preview_final":
    st.subheader("4. Preview Final")
    st.info("Próxima etapa do rebuild: download idêntico ao modelo.")
    render_topo_navegacao()

