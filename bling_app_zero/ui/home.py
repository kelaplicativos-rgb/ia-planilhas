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


def _query_param(name: str) -> str:
    try:
        value = st.query_params.get(name, '')
        if isinstance(value, list):
            return str(value[0] if value else '')
        return str(value or '')
    except Exception:
        return ''


def _default_home_index() -> int:
    flow = _query_param('flow').lower().strip()
    if flow in {'site', 'cadastro_site', 'estoque_site'}:
        return list(OPERACOES.values()).index('site')
    if flow == 'estoque':
        return list(OPERACOES.values()).index('estoque')
    if flow == 'cadastro':
        return list(OPERACOES.values()).index('cadastro')
    return 0


def render_home() -> None:
    inject_clean_home_css()
    render_compact_hero()
    render_diagnostics_panel()

    render_step_title('O que você deseja fazer?')
    escolha = st.radio(
        'Escolha o fluxo principal',
        list(OPERACOES.keys()),
        index=_default_home_index(),
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
