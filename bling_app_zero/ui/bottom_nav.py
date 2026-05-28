from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.scroll_position import request_scroll_top

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
FLOW_HOME = 'home'
FLOW_WIZARD = 'wizard_cadastro_estoque'


def _clear_navigation_params() -> None:
    try:
        for key in ('operation_v2', 'step', 'flow', 'origem', 'operacao', 'operation'):
            st.query_params.pop(key, None)
    except Exception:
        pass


def _go_home() -> None:
    request_scroll_top()
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_HOME
    st.session_state[HOME_ALLOW_FLOW_KEY] = False
    st.session_state['home_single_page_flow_active'] = False
    _clear_navigation_params()


def _set_wizard(step: str | None = None) -> None:
    request_scroll_top()
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_WIZARD
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    st.session_state['home_single_page_flow_active'] = True
    if step:
        st.session_state['bling_wizard_step'] = step
    try:
        st.query_params['operation_v2'] = FLOW_WIZARD
        if step:
            st.query_params['step'] = step
        else:
            st.query_params.pop('step', None)
        for key in ('flow', 'origem', 'operacao', 'operation'):
            st.query_params.pop(key, None)
    except Exception:
        pass


def render_bottom_nav() -> None:
    st.markdown('---')
    st.caption('Menu rápido do sistema')
    col1, col2 = st.columns(2)

    with col1:
        if st.button('Home', key='bottom_nav_home', use_container_width=True):
            _go_home()
            st.rerun()

    with col2:
        if st.button('Fluxo Universal', key='bottom_nav_universal', use_container_width=True):
            _set_wizard('modelo')
            st.rerun()


__all__ = ['render_bottom_nav']
