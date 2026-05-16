from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.universal_flow import render_universal_flow

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
FLOW_UNIVERSAL = 'universal_model_flow'
LEGACY_FLOWS = {'wizard_cadastro_estoque', 'price_multistore_v2'}
RESPONSIBLE_FILE = 'bling_app_zero/ui/home_router.py'


def _set_flow(flow: str) -> None:
    safe_flow = FLOW_UNIVERSAL if flow in LEGACY_FLOWS else flow
    previous = st.session_state.get(ACTIVE_FLOW_KEY)
    st.session_state[ACTIVE_FLOW_KEY] = safe_flow
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    add_audit_event(
        'home_operation_selected',
        area='HOME',
        details={'previous': previous, 'selected': safe_flow, 'requested': flow, 'responsible_file': RESPONSIBLE_FILE},
    )
    try:
        st.query_params['operation_v2'] = safe_flow
    except Exception:
        pass
    st.rerun()


def _clear_flow_query_param() -> None:
    for key in ('operation_v2', 'step', 'flow', 'origem', 'operacao'):
        try:
            st.query_params.pop(key, None)
        except Exception:
            pass


def _current_flow() -> str:
    allowed = bool(st.session_state.get(HOME_ALLOW_FLOW_KEY))
    flow = str(st.session_state.get(ACTIVE_FLOW_KEY) or '').strip()
    if allowed and flow:
        if flow in LEGACY_FLOWS:
            st.session_state[ACTIVE_FLOW_KEY] = FLOW_UNIVERSAL
            add_audit_event(
                'legacy_flow_redirected_to_universal',
                area='HOME',
                details={'legacy_flow': flow, 'responsible_file': RESPONSIBLE_FILE},
            )
            return FLOW_UNIVERSAL
        return flow

    stale_flow = st.session_state.pop(ACTIVE_FLOW_KEY, None)
    st.session_state.pop(HOME_ALLOW_FLOW_KEY, None)
    _clear_flow_query_param()
    if stale_flow:
        add_audit_event(
            'home_stale_flow_cleared',
            area='HOME',
            details={'reason': 'home_must_start_on_universal_choice', 'stale_flow': stale_flow, 'responsible_file': RESPONSIBLE_FILE},
        )
    return ''


def _open_universal_flow() -> None:
    _set_flow(FLOW_UNIVERSAL)


def _render_action_card(*, icon: str, title: str, hint: str, button_label: str, button_key: str, on_click: Callable[[], None]) -> None:
    with st.container(border=True):
        st.markdown(f'### {icon} {title}')
        st.caption(hint)
        if st.button(button_label, use_container_width=True, key=button_key):
            on_click()


def _render_operation_choice() -> None:
    st.markdown('## O que você quer fazer?')
    _render_action_card(
        icon='🧭',
        title='Preencher qualquer modelo',
        hint='Anexe o modelo de destino e uma origem. A planilha final sai no mesmo formato do modelo, seja cadastro, estoque, preços, multilojas ou qualquer outro layout.',
        button_label='Começar pelo modelo de destino',
        button_key='home_open_universal_flow',
        on_click=_open_universal_flow,
    )
    st.caption('Fluxo antigo extinto: cadastro, estoque e preços agora são tipos detectados dentro do modelo universal.')


def _back_to_operations() -> None:
    st.session_state.pop(ACTIVE_FLOW_KEY, None)
    st.session_state.pop(HOME_ALLOW_FLOW_KEY, None)
    _clear_flow_query_param()
    add_audit_event('home_operation_cleared', area='HOME', details={'universal_flow_only': True, 'responsible_file': RESPONSIBLE_FILE})
    st.rerun()


def _render_back_to_operations() -> None:
    if st.button('← Voltar', use_container_width=True, key='home_back_to_operation_choice'):
        _back_to_operations()


def render_home_router() -> None:
    flow = _current_flow()
    if not flow:
        _render_operation_choice()
        return

    _render_back_to_operations()
    render_universal_flow()


__all__ = ['render_home_router']
