import streamlit as st

from bling_app_zero.utils.init_app import init_app
from bling_app_zero.ui.app_core_state import init_state
from bling_app_zero.ui.app_core_layout import render_header, render_nav
from bling_app_zero.ui.app_core_flow import set_etapa_segura, sincronizar_fluxo_inicial
from bling_app_zero.ui.health_panel import render_health_panel
from bling_app_zero.ui.step_router import render_step


def trocar_etapa(etapa):
    set_etapa_segura(etapa, origem="nav")


def main():
    st.set_page_config(page_title="IA Planilhas Bling", page_icon="🚀", layout="wide")
    init_app()
    init_state()
    sincronizar_fluxo_inicial()
    etapa = st.session_state.get("wizard_etapa_atual", "origem")
    etapa_max = st.session_state.get("wizard_etapa_maxima", "origem")
    render_header()
    render_health_panel()
    render_nav(etapa, etapa_max, trocar_etapa)
    render_step(etapa)


if __name__ == "__main__":
    main()
