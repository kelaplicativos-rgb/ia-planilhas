from __future__ import annotations

import streamlit as st

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
FLOW_WIZARD = 'wizard_cadastro_estoque'
FLOW_PRICE_UPDATE = 'price_multistore_v2'
FLOW_LINKS_UTEIS = 'links_uteis'
FLOW_MODELOS_BLING = 'modelos_bling'


def _set_flow(flow: str, step: str | None = None) -> None:
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
    except Exception:
        pass


def _active_flow() -> str:
    try:
        query_flow = str(st.query_params.get('operation_v2') or '').strip()
    except Exception:
        query_flow = ''
    return query_flow or str(st.session_state.get(ACTIVE_FLOW_KEY) or FLOW_WIZARD).strip() or FLOW_WIZARD


def render_bottom_nav() -> None:
    _ = _active_flow()
    st.markdown('---')
    st.caption('Menu rápido do sistema')
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button('Preços multiloja', key='bottom_nav_precos', use_container_width=True):
            _set_flow(FLOW_PRICE_UPDATE)
            st.rerun()

    with col2:
        if st.button('Modelos Bling', key='bottom_nav_bling', use_container_width=True):
            _set_flow(FLOW_MODELOS_BLING)
            st.rerun()

    with col3:
        if st.button('Modelo universal', key='bottom_nav_universal', use_container_width=True):
            _set_flow(FLOW_WIZARD, 'modelo')
            st.rerun()


__all__ = ['render_bottom_nav']
