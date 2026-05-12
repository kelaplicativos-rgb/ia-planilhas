from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_wizard import render_home_wizard
from bling_app_zero.v2.price_multistore.ui import render_price_multistore_v2

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
FLOW_WIZARD = 'wizard_cadastro_estoque'
FLOW_PRICE_MULTISTORE = 'price_multistore_v2'
RESPONSIBLE_FILE = 'bling_app_zero/ui/home_router.py'


def _set_flow(flow: str) -> None:
    previous = st.session_state.get(ACTIVE_FLOW_KEY)
    st.session_state[ACTIVE_FLOW_KEY] = flow
    add_audit_event(
        'home_operation_selected',
        area='HOME',
        details={'previous': previous, 'selected': flow, 'responsible_file': RESPONSIBLE_FILE},
    )
    try:
        st.query_params['operation_v2'] = flow
    except Exception:
        pass
    st.rerun()


def _current_flow() -> str:
    flow = str(st.session_state.get(ACTIVE_FLOW_KEY) or '').strip()
    if flow:
        return flow
    try:
        qp_flow = str(st.query_params.get('operation_v2', '') or '').strip()
        if qp_flow:
            st.session_state[ACTIVE_FLOW_KEY] = qp_flow
            return qp_flow
    except Exception:
        pass
    return ''


def _render_operation_choice() -> None:
    st.markdown('### O que você quer fazer?')
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown('**🧾 Cadastrar produtos**')
        st.caption('Fluxo atual para gerar CSV de cadastro de produtos no Bling.')
        if st.button('Abrir cadastro', use_container_width=True, key='home_open_cadastro_flow'):
            st.session_state['home_slim_flow_operation'] = 'cadastro'
            _set_flow(FLOW_WIZARD)
    with c2:
        st.markdown('**📦 Atualizar estoque**')
        st.caption('Fluxo atual para gerar CSV de atualização de saldo/depósito.')
        if st.button('Abrir estoque', use_container_width=True, key='home_open_estoque_flow'):
            st.session_state['home_slim_flow_operation'] = 'estoque'
            _set_flow(FLOW_WIZARD)
    with c3:
        st.markdown('**🏬 Atualizar preços multilojas**')
        st.caption('Novo fluxo V2 para marketplace, ID na Loja, preço e preço promocional.')
        if st.button('Abrir preços multilojas V2', use_container_width=True, key='home_open_multistore_price_flow'):
            _set_flow(FLOW_PRICE_MULTISTORE)


def _render_back_to_operations() -> None:
    if st.button('← Voltar para escolha da operação', use_container_width=True, key='home_back_to_operation_choice'):
        st.session_state.pop(ACTIVE_FLOW_KEY, None)
        try:
            st.query_params.pop('operation_v2', None)
        except Exception:
            pass
        add_audit_event('home_operation_cleared', area='HOME', details={'responsible_file': RESPONSIBLE_FILE})
        st.rerun()


def render_home_router() -> None:
    flow = _current_flow()
    if not flow:
        _render_operation_choice()
        return

    _render_back_to_operations()
    if flow == FLOW_PRICE_MULTISTORE:
        render_price_multistore_v2()
        return

    render_home_wizard()


__all__ = ['render_home_router']
