import streamlit as st

from bling_app_zero.utils.init_app import init_app
from bling_app_zero.ui.app_helpers import (
    get_etapa,
    render_topo_navegacao,
    sincronizar_etapa_da_url,
)
from bling_app_zero.ui.origem_dados import render_origem_dados
from bling_app_zero.ui.origem_precificacao import render_origem_precificacao
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.ui.preview_final import render_preview_final

init_app()

st.set_page_config(
    page_title="IA Planilhas → Bling",
    layout="wide",
)

sincronizar_etapa_da_url()

st.title("🚀 IA Planilhas → Bling")
render_topo_navegacao()

etapa = get_etapa()

if etapa == "origem":
    render_origem_dados()

elif etapa == "precificacao":
    render_origem_precificacao()

elif etapa == "mapeamento":
    render_origem_mapeamento()

elif etapa == "preview_final":
    render_preview_final()
