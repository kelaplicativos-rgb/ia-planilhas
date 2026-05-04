import streamlit as st

from bling_app_zero.utils.init_app import init_app
from bling_app_zero.ui.app_core_state import init_state
from bling_app_zero.ui.app_core_layout import render_header, render_nav
from bling_app_zero.ui.app_core_flow import set_etapa_segura, sincronizar_fluxo_inicial

from bling_app_zero.ui.origem_dados_sem_estoque import render_origem_dados
from bling_app_zero.ui.origem_precificacao import render_origem_precificacao
from bling_app_zero.ui.origem_mapeamento import render_origem_mapeamento
from bling_app_zero.ui.preview_final import render_preview_final


def render_etapa(etapa):
    if etapa == "origem":
        render_origem_dados()
    elif etapa == "precificacao":
        render_origem_precificacao()
    elif etapa == "mapeamento":
        render_origem_mapeamento()
    elif etapa == "preview_final":
        render_preview_final()


def trocar_etapa(etapa):
    set_etapa_segura(etapa, origem="nav")


def main():
    st.set_page_config(page_title="IA Planilhas → Bling", page_icon="🚀", layout="wide")

    init_app()
    init_state()
    sincronizar_fluxo_inicial()

    etapa = st.session_state.get("wizard_etapa_atual", "origem")
    etapa_max = st.session_state.get("wizard_etapa_maxima", "origem")

    render_header()
    render_nav(etapa, etapa_max, trocar_etapa)
    render_etapa(etapa)


if __name__ == "__main__":
    main()
