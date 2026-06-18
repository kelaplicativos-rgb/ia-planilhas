from __future__ import annotations

import streamlit as st

import bling_app_zero.ui.home_router as legacy
from bling_app_zero.ui.home_wizard_v2 import STEP_CATEGORIZACAO, render_home_wizard
from bling_app_zero.v2.price_multistore.ui_plus import render_price_multistore_v2

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_router_v2.py'
ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
FLOW_HOME = 'home'
FLOW_PRICE_UPDATE = 'price_multistore_v2'

# O router legado importa render_home_wizard uma vez. Este patch troca a rota por uma
# versão que contém a etapa independente de Conferência e Correção de Categorias.
legacy.render_home_wizard = render_home_wizard
try:
    legacy.VALID_SINGLE_PAGE_STEPS.add(STEP_CATEGORIZACAO)
except Exception:
    pass


def _query_param(name: str) -> str:
    try:
        value = st.query_params.get(name)
    except Exception:
        return ''
    if isinstance(value, list):
        return str(value[0] if value else '').strip()
    return str(value or '').strip()


def start_price_multistore_flow() -> None:
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_PRICE_UPDATE
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    st.session_state['home_single_page_flow_active'] = False
    try:
        st.query_params['operation_v2'] = FLOW_PRICE_UPDATE
        st.query_params.pop('step', None)
    except Exception:
        pass


def _price_multistore_requested() -> bool:
    return _query_param('operation_v2') == FLOW_PRICE_UPDATE or str(st.session_state.get(ACTIVE_FLOW_KEY) or '') == FLOW_PRICE_UPDATE


def _go_home_from_price_multistore() -> None:
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_HOME
    st.session_state[HOME_ALLOW_FLOW_KEY] = False
    try:
        st.query_params.pop('operation_v2', None)
        st.query_params.pop('step', None)
    except Exception:
        pass
    st.rerun()


def _render_price_multistore_route() -> None:
    start_price_multistore_flow()
    st.session_state['price_multistore_independent_route_active'] = True
    col_back, col_title = st.columns([1, 3])
    with col_back:
        if st.button('Voltar ao início', use_container_width=True, key='price_multistore_back_home_v2'):
            _go_home_from_price_multistore()
    with col_title:
        st.caption('Fluxo independente: não passa por cadastro, estoque, categorias ou Regras e IA.')
    render_price_multistore_v2()


def _render_price_multistore_home_entry() -> None:
    active_flow = str(st.session_state.get(ACTIVE_FLOW_KEY) or FLOW_HOME).strip()
    if active_flow not in {'', FLOW_HOME}:
        return
    st.markdown('---')
    st.markdown('### Fluxo independente')
    st.caption('Use este caminho somente para atualizar preços por loja/canal. Ele não passa pelo wizard de cadastro/estoque.')
    if st.button('Atualizar preços multilojas', use_container_width=True, key='home_start_price_multistore_v2'):
        start_price_multistore_flow()
        st.rerun()


def render_home() -> None:
    if _price_multistore_requested():
        _render_price_multistore_route()
        return
    legacy.render_home()
    _render_price_multistore_home_entry()


__all__ = ['FLOW_PRICE_UPDATE', 'render_home', 'start_price_multistore_flow']
