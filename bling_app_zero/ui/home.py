from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.cadastro_panel import render_cadastro_panel
from bling_app_zero.ui.clean_layout import inject_clean_home_css, render_compact_hero, render_step_title
from bling_app_zero.ui.diagnostics_panel import render_diagnostics_panel
from bling_app_zero.ui.estoque_panel import render_estoque_panel
from bling_app_zero.ui.site_panel import render_site_panel


OPERACOES = {
    'Cadastro de Produtos': 'cadastro',
    'Atualização de Estoque': 'estoque',
    'Busca Inteligente por Site': 'site',
}


def render_home() -> None:
    inject_clean_home_css()
    render_compact_hero()
    render_diagnostics_panel()

    render_step_title('O que você deseja fazer?')
    escolha = st.radio(
        'Escolha o fluxo principal',
        list(OPERACOES.keys()),
        horizontal=False,
        label_visibility='collapsed',
        key='home_tipo_operacao_radio',
    )
    operacao = OPERACOES[escolha]
    st.session_state['tipo_operacao'] = operacao

    if operacao == 'cadastro':
        render_cadastro_panel()
        return

    if operacao == 'estoque':
        render_estoque_panel()
        return

    if operacao == 'site':
        render_site_panel()
        return
