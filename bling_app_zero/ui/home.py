from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.cadastro_panel import render_cadastro_panel
from bling_app_zero.ui.estoque_panel import render_estoque_panel
from bling_app_zero.ui.site_panel import render_site_panel


OPERACOES = {
    'Cadastro de Produtos': 'cadastro',
    'Atualização de Estoque': 'estoque',
    'Busca Inteligente por Site': 'site',
}


def render_home() -> None:
    st.title('🚀 IA Planilhas → Bling')
    st.markdown('### Plataforma inteligente de integração, captura, transformação e automação de dados para o ERP Bling')

    escolha = st.radio('O que você deseja fazer?', list(OPERACOES.keys()), horizontal=True)
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
