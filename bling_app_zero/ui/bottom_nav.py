from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.scroll_position import request_scroll_top

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
FLOW_HOME = 'home'
FLOW_WIZARD = 'wizard_cadastro_estoque'
FLOW_PRICE_UPDATE = 'price_multistore_v2'
FLOW_LINKS_UTEIS = 'links_uteis'
FLOW_MODELOS_BLING = 'modelos_bling'


def _clear_navigation_params() -> None:
    try:
        for key in ('operation_v2', 'step', 'flow', 'origem', 'operacao'):
            st.query_params.pop(key, None)
    except Exception:
        pass


def _go_home() -> None:
    request_scroll_top()
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_HOME
    st.session_state[HOME_ALLOW_FLOW_KEY] = False
    st.session_state['home_single_page_flow_active'] = False
    _clear_navigation_params()


def _set_flow(flow: str, step: str | None = None) -> None:
    request_scroll_top()
    st.session_state[ACTIVE_FLOW_KEY] = flow
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    st.session_state['home_single_page_flow_active'] = flow == FLOW_WIZARD
    if step:
        st.session_state['bling_wizard_step'] = step
    try:
        st.query_params['operation_v2'] = flow
        if step:
            st.query_params['step'] = step
        else:
            st.query_params.pop('step', None)
        for key in ('flow', 'origem', 'operacao'):
            st.query_params.pop(key, None)
    except Exception:
        pass


def _active_flow() -> str:
    try:
        query_flow = str(st.query_params.get('operation_v2') or '').strip()
    except Exception:
        query_flow = ''
    return query_flow or str(st.session_state.get(ACTIVE_FLOW_KEY) or FLOW_HOME).strip() or FLOW_HOME


def render_bottom_nav() -> None:
    _ = _active_flow()
    st.markdown('---')
    st.caption('Menu rápido do sistema')
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button('Home', key='bottom_nav_home', use_container_width=True):
            _go_home()
            st.rerun()

    with col2:
        if st.button('Calculadora', key='bottom_nav_calculadora', use_container_width=True):
            _set_flow(FLOW_PRICE_UPDATE)
            st.rerun()

    with col3:
        if st.button('Bling', key='bottom_nav_bling', use_container_width=True):
            _set_flow(FLOW_MODELOS_BLING)
            st.rerun()

    with col4:
        if st.button('Universal', key='bottom_nav_universal', use_container_width=True):
            _set_flow(FLOW_WIZARD, 'modelo')
            st.rerun()


__all__ = ['render_bottom_nav']
