from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_wizard import render_home_wizard
from bling_app_zero.ui.links_uteis import render_links_uteis
from bling_app_zero.ui.modelos_bling import render_modelos_bling
from bling_app_zero.v2.price_multistore.ui import render_price_multistore_v2

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
FLOW_WIZARD = 'wizard_cadastro_estoque'
FLOW_PRICE_UPDATE = 'price_multistore_v2'
FLOW_LINKS_UTEIS = 'links_uteis'
FLOW_MODELOS_BLING = 'modelos_bling'
RESPONSIBLE_FILE = 'bling_app_zero/ui/home_router.py'
WIZARD_STEP_KEY = 'bling_wizard_step'
STEP_MODELO = 'modelo'
STEP_ORIGEM = 'origem'
VALID_SINGLE_PAGE_STEPS = {
    STEP_MODELO,
    STEP_ORIGEM,
    'entrada',
    'precificacao',
    'mapeamento',
    'preview',
    'download',
    'regras',
    'gerar_estoque',
}


def _query_param(name: str) -> str:
    try:
        value = st.query_params.get(name)
    except Exception:
        return ''
    if isinstance(value, list):
        return str(value[0] if value else '').strip()
    return str(value or '').strip()


def _current_wizard_step() -> str:
    query_step = _query_param('step').lower()
    if query_step in VALID_SINGLE_PAGE_STEPS:
        st.session_state[WIZARD_STEP_KEY] = query_step
        return query_step

    step = str(st.session_state.get(WIZARD_STEP_KEY) or '').strip().lower()
    return step if step in VALID_SINGLE_PAGE_STEPS else ''


def _set_single_page_wizard_state() -> None:
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_WIZARD
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    st.session_state['home_single_page_flow_active'] = True

    current_step = _current_wizard_step()
    if not current_step:
        st.session_state[WIZARD_STEP_KEY] = STEP_MODELO
        current_step = STEP_MODELO

    try:
        st.query_params['operation_v2'] = FLOW_WIZARD
        st.query_params['step'] = current_step
        for key in ('flow', 'origem', 'operacao'):
            st.query_params.pop(key, None)
    except Exception:
        pass


def _requested_flow() -> str:
    query_flow = _query_param('operation_v2')
    if query_flow:
        return query_flow

    flow = str(st.session_state.get(ACTIVE_FLOW_KEY) or '').strip()
    if flow:
        return flow

    return FLOW_WIZARD


def _activate_non_wizard_flow(flow: str) -> None:
    st.session_state[ACTIVE_FLOW_KEY] = flow
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    st.session_state['home_single_page_flow_active'] = True

    try:
        st.query_params['operation_v2'] = flow
        st.query_params.pop('step', None)
        for key in ('flow', 'origem', 'operacao'):
            st.query_params.pop(key, None)
    except Exception:
        pass


def render_home_router() -> None:
    st.session_state['home_single_page_flow_active'] = True
    requested_flow = _requested_flow()

    if requested_flow == FLOW_PRICE_UPDATE:
        _activate_non_wizard_flow(FLOW_PRICE_UPDATE)
        add_audit_event(
            'home_router_render_price_update',
            area='HOME',
            details={'responsible_file': RESPONSIBLE_FILE},
        )
        render_price_multistore_v2()
        return

    if requested_flow == FLOW_LINKS_UTEIS:
        _activate_non_wizard_flow(FLOW_LINKS_UTEIS)
        add_audit_event(
            'home_router_render_links_uteis',
            area='HOME',
            details={'responsible_file': RESPONSIBLE_FILE},
        )
        render_links_uteis()
        return

    if requested_flow == FLOW_MODELOS_BLING:
        _activate_non_wizard_flow(FLOW_MODELOS_BLING)
        add_audit_event(
            'home_router_render_modelos_bling',
            area='HOME',
            details={'responsible_file': RESPONSIBLE_FILE},
        )
        render_modelos_bling()
        return

    _set_single_page_wizard_state()
    add_audit_event(
        'home_router_render_single_page_wizard',
        area='HOME',
        details={
            'responsible_file': RESPONSIBLE_FILE,
            'wizard_step': st.session_state.get(WIZARD_STEP_KEY),
            'step_preserved': True,
            'bottom_nav_enabled': True,
        },
    )
    render_home_wizard()


__all__ = [
    'FLOW_LINKS_UTEIS',
    'FLOW_MODELOS_BLING',
    'FLOW_PRICE_UPDATE',
    'FLOW_WIZARD',
    'render_home_router',
]
