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


def _set_single_page_wizard_state() -> None:
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_WIZARD
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    st.session_state[WIZARD_STEP_KEY] = STEP_ORIGEM
    st.session_state['home_single_page_flow_active'] = True
    try:
        st.query_params['operation_v2'] = FLOW_WIZARD
        st.query_params['step'] = STEP_ORIGEM
        for key in ('flow', 'origem', 'operacao'):
            st.query_params.pop(key, None)
    except Exception:
        pass


def _requested_flow() -> str:
    flow = str(st.session_state.get(ACTIVE_FLOW_KEY) or '').strip()
    if flow:
        return flow
    try:
        return str(st.query_params.get('operation_v2') or '').strip()
    except Exception:
        return ''


def render_home_router() -> None:
    st.session_state['home_single_page_flow_active'] = True

    if _requested_flow() == FLOW_PRICE_UPDATE:
        st.session_state[ACTIVE_FLOW_KEY] = FLOW_PRICE_UPDATE
        st.session_state[HOME_ALLOW_FLOW_KEY] = True
        add_audit_event(
            'home_router_render_price_update',
            area='HOME',
            details={'responsible_file': RESPONSIBLE_FILE},
        )
        render_price_multistore_v2()
        return

    _set_single_page_wizard_state()
    add_audit_event(
        'home_router_render_single_page_wizard',
        area='HOME',
        details={'responsible_file': RESPONSIBLE_FILE},
    )
    render_home_wizard()


__all__ = ['FLOW_PRICE_UPDATE', 'FLOW_WIZARD', 'render_home_router']
