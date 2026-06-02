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


def render_bottom_nav() -> None:
    active_flow = str(st.session_state.get(ACTIVE_FLOW_KEY) or '').strip()
    if active_flow in {'', FLOW_HOME}:
        return

    st.markdown('---')
    if st.button('⬅️ Voltar para o início', key='bottom_nav_home', use_container_width=True):
        _go_home()
        st.rerun()


__all__ = ['render_bottom_nav']
