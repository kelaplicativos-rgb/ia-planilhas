from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.home_wizard import render_home_wizard
from bling_app_zero.ui.links_uteis import render_links_uteis
from bling_app_zero.ui.modelos_bling import render_modelos_bling
from bling_app_zero.v2.price_multistore.ui import render_price_multistore_v2

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
HOME_BOOT_LOCK_KEY = 'home_boot_landing_rendered_once'
FLOW_HOME = 'home'
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


def _clear_navigation_params() -> None:
    try:
        for key in ('operation_v2', 'step', 'flow', 'origem', 'operacao'):
            st.query_params.pop(key, None)
    except Exception:
        pass


def _set_home_flow() -> None:
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_HOME
    st.session_state[HOME_ALLOW_FLOW_KEY] = False
    st.session_state['home_single_page_flow_active'] = False
    _clear_navigation_params()


def _set_flow(flow: str, step: str | None = None) -> None:
    st.session_state[ACTIVE_FLOW_KEY] = flow
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    st.session_state['home_single_page_flow_active'] = flow == FLOW_WIZARD
    if step:
        st.session_state[WIZARD_STEP_KEY] = step
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
    if not bool(st.session_state.get(HOME_BOOT_LOCK_KEY)):
        st.session_state[HOME_BOOT_LOCK_KEY] = True
        _set_home_flow()
        return FLOW_HOME

    query_flow = _query_param('operation_v2')
    allow_flow = bool(st.session_state.get(HOME_ALLOW_FLOW_KEY, False))
    if query_flow and allow_flow:
        return query_flow

    flow = str(st.session_state.get(ACTIVE_FLOW_KEY) or '').strip()
    if flow:
        return flow

    return FLOW_HOME


def _activate_non_wizard_flow(flow: str) -> None:
    st.session_state[ACTIVE_FLOW_KEY] = flow
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    st.session_state['home_single_page_flow_active'] = False

    try:
        st.query_params['operation_v2'] = flow
        st.query_params.pop('step', None)
        for key in ('flow', 'origem', 'operacao'):
            st.query_params.pop(key, None)
    except Exception:
        pass


def _render_home_card(title: str, subtitle: str, button: str, flow: str, *, step: str | None = None, key: str) -> None:
    with st.container(border=True):
        st.markdown(f'#### {title}')
        st.caption(subtitle)
        if st.button(button, use_container_width=True, key=key):
            _set_flow(flow, step)
            st.rerun()


def render_professional_home() -> None:
    add_audit_event(
        'home_router_render_professional_home',
        area='HOME',
        status='OK',
        details={'responsible_file': RESPONSIBLE_FILE},
    )

    st.markdown('### Comece pelo fluxo certo')
    st.caption('A home é o ponto inicial do sistema. Escolha uma operação abaixo para abrir o módulo somente quando precisar.')

    col1, col2 = st.columns(2)
    with col1:
        _render_home_card(
            'Modelo universal',
            'Transforme planilhas, XML, PDF ou dados de site no modelo final anexado.',
            'Abrir fluxo universal',
            FLOW_WIZARD,
            step=STEP_MODELO,
            key='home_card_open_universal',
        )
    with col2:
        _render_home_card(
            'Calculadora principal',
            'Central para cálculos rápidos, edição de taxas e adição de marketplaces.',
            'Abrir calculadora',
            FLOW_PRICE_UPDATE,
            key='home_card_open_calculator',
        )

    col3, col4 = st.columns(2)
    with col3:
        _render_home_card(
            'Bling',
            'Modelos, importadores, ajuda e atalhos oficiais do Bling em uma única aba.',
            'Abrir Bling',
            FLOW_MODELOS_BLING,
            key='home_card_open_bling',
        )
    with col4:
        _render_home_card(
            'Sistema',
            'Links do app publicado e repositório, sem misturar com os atalhos do Bling.',
            'Abrir sistema',
            FLOW_LINKS_UTEIS,
            key='home_card_open_system_links',
        )

    st.info('Nenhum módulo é aberto automaticamente. O sistema sempre nasce na home e só entra em um fluxo após sua escolha.')


def render_home_router() -> None:
    requested_flow = _requested_flow()

    if requested_flow in {'', FLOW_HOME}:
        _set_home_flow()
        render_professional_home()
        return

    if requested_flow == FLOW_PRICE_UPDATE:
        _activate_non_wizard_flow(FLOW_PRICE_UPDATE)
        add_audit_event(
            'home_router_render_price_update',
            area='HOME',
            details={'responsible_file': RESPONSIBLE_FILE, 'module_label': 'calculadora_principal'},
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
    'FLOW_HOME',
    'FLOW_LINKS_UTEIS',
    'FLOW_MODELOS_BLING',
    'FLOW_PRICE_UPDATE',
    'FLOW_WIZARD',
    'render_home_router',
    'render_professional_home',
]
