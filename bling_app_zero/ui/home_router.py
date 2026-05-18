from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_wizard import render_home_wizard
from bling_app_zero.v2.price_multistore.ui import render_price_multistore_v2

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
FLOW_WIZARD = 'wizard_cadastro_estoque'
FLOW_PRICE_UPDATE = 'price_multistore_v2'
RESPONSIBLE_FILE = 'bling_app_zero/ui/home_router.py'
WIZARD_STEP_KEY = 'bling_wizard_step'
STEP_ORIGEM = 'origem'
SINGLE_PAGE_FLOW = True


def _activate_main_flow() -> None:
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_WIZARD
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    st.session_state[WIZARD_STEP_KEY] = STEP_ORIGEM
    st.session_state['home_single_page_flow_active'] = True
    try:
        st.query_params['operation_v2'] = FLOW_WIZARD
        st.query_params['step'] = STEP_ORIGEM
    except Exception:
        pass


def _clear_flow_query_param() -> None:
    for key in ('operation_v2', 'step', 'flow', 'origem', 'operacao'):
        try:
            st.query_params.pop(key, None)
        except Exception:
            pass


def _current_flow() -> str:
    allowed = bool(st.session_state.get(HOME_ALLOW_FLOW_KEY))
    flow = str(st.session_state.get(ACTIVE_FLOW_KEY) or '').strip()
    if not flow:
        try:
            flow = str(st.query_params.get('operation_v2') or '').strip()
        except Exception:
            flow = ''
        if flow:
            st.session_state[ACTIVE_FLOW_KEY] = flow
            st.session_state[HOME_ALLOW_FLOW_KEY] = True
            allowed = True

    if allowed and flow:
        if flow in {FLOW_WIZARD, FLOW_PRICE_UPDATE}:
            return flow
        return FLOW_WIZARD

    stale_flow = st.session_state.pop(ACTIVE_FLOW_KEY, None)
    st.session_state.pop(HOME_ALLOW_FLOW_KEY, None)
    _clear_flow_query_param()
    if stale_flow:
        add_audit_event(
            'home_stale_flow_cleared',
            area='HOME',
            details={'reason': 'home_single_page_start', 'stale_flow': stale_flow, 'responsible_file': RESPONSIBLE_FILE},
        )
    return ''


def render_home_router() -> None:
    st.session_state['home_single_page_flow_active'] = True

    flow = _current_flow()
    if flow == FLOW_PRICE_UPDATE:
        render_price_multistore_v2()
        return

    _activate_main_flow()
    render_home_wizard()


__all__ = ['FLOW_PRICE_UPDATE', 'FLOW_WIZARD', 'render_home_router']
