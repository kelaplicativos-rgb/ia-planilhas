from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_oauth import build_authorization_url, connection_status
from bling_app_zero.ui.home_wizard import render_home_wizard
from bling_app_zero.ui.links_uteis import render_links_uteis
from bling_app_zero.ui.modelos_bling import render_modelos_bling
from bling_app_zero.ui.scroll_position import request_scroll_top
from bling_app_zero.v2.price_multistore.quick_ui import render_quick_price_calculator
from bling_app_zero.v2.price_multistore.ui import render_price_multistore_v2

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
HOME_BOOT_LOCK_KEY = 'home_boot_landing_rendered_once'
HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
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
    if query_step == 'gerar_estoque':
        st.session_state[WIZARD_STEP_KEY] = STEP_ORIGEM
        return STEP_ORIGEM
    if query_step in VALID_SINGLE_PAGE_STEPS:
        st.session_state[WIZARD_STEP_KEY] = query_step
        return query_step

    step = str(st.session_state.get(WIZARD_STEP_KEY) or '').strip().lower()
    if step == 'gerar_estoque':
        st.session_state[WIZARD_STEP_KEY] = STEP_ORIGEM
        return STEP_ORIGEM
    return step if step in VALID_SINGLE_PAGE_STEPS else ''


def _clear_navigation_params() -> None:
    try:
        for key in ('operation_v2', 'step', 'flow', 'origem', 'operacao', 'operation'):
            st.query_params.pop(key, None)
    except Exception:
        pass


def _set_home_flow() -> None:
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_HOME
    st.session_state[HOME_ALLOW_FLOW_KEY] = False
    st.session_state['home_single_page_flow_active'] = False
    st.session_state.pop(HOME_ENTRY_CONTEXT_KEY, None)
    _clear_navigation_params()


def _start_wizard_context(context: str, *, step: str | None = None) -> None:
    request_scroll_top()
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_WIZARD
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    st.session_state['home_single_page_flow_active'] = True
    st.session_state[HOME_ENTRY_CONTEXT_KEY] = context

    if context == 'bling_api':
        st.session_state.pop('bling_finish_mode', None)
        st.session_state.pop('skip_direct_bling_connection_this_flow', None)
        st.session_state.pop(WIZARD_STEP_KEY, None)
    elif context in {'bling_csv', 'universal'}:
        st.session_state['bling_finish_mode'] = 'csv_download'
        st.session_state['skip_direct_bling_connection_this_flow'] = True
        st.session_state[WIZARD_STEP_KEY] = step or STEP_MODELO
    elif step:
        st.session_state[WIZARD_STEP_KEY] = step
    else:
        st.session_state.pop(WIZARD_STEP_KEY, None)

    try:
        st.query_params['operation_v2'] = FLOW_WIZARD
        active_step = st.session_state.get(WIZARD_STEP_KEY)
        if active_step:
            st.query_params['step'] = str(active_step)
        else:
            st.query_params.pop('step', None)
        for key in ('flow', 'origem', 'operacao', 'operation'):
            st.query_params.pop(key, None)
    except Exception:
        pass


def _set_flow(flow: str, step: str | None = None) -> None:
    request_scroll_top()
    st.session_state[ACTIVE_FLOW_KEY] = flow
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    st.session_state['home_single_page_flow_active'] = flow == FLOW_WIZARD
    if step:
        st.session_state[WIZARD_STEP_KEY] = step
    else:
        st.session_state.pop(WIZARD_STEP_KEY, None)
    try:
        st.query_params['operation_v2'] = flow
        if step:
            st.query_params['step'] = step
        else:
            st.query_params.pop('step', None)
        for key in ('flow', 'origem', 'operacao', 'operation'):
            st.query_params.pop(key, None)
    except Exception:
        pass


def _set_single_page_wizard_state() -> None:
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_WIZARD
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    st.session_state['home_single_page_flow_active'] = True

    current_step = _current_wizard_step()
    try:
        st.query_params['operation_v2'] = FLOW_WIZARD
        if current_step:
            st.query_params['step'] = current_step
        else:
            st.query_params.pop('step', None)
        for key in ('flow', 'origem', 'operacao', 'operation'):
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
        for key in ('flow', 'origem', 'operacao', 'operation'):
            st.query_params.pop(key, None)
    except Exception:
        pass


def _render_home_card(
    title: str,
    subtitle: str,
    button: str,
    *,
    context: str | None = None,
    flow: str = FLOW_WIZARD,
    step: str | None = None,
    key: str,
    badge: str = '',
    note: str = '',
) -> None:
    with st.container(border=True):
        if badge:
            st.caption(badge)
        st.markdown(f'#### {title}')
        st.caption(subtitle)
        if note:
            st.caption(note)
        if st.button(button, use_container_width=True, key=key):
            if context:
                _start_wizard_context(context, step=step)
            else:
                _set_flow(flow, step)
            st.rerun()


def _render_bling_api_home_card() -> None:
    with st.container(border=True):
        st.caption('Mais automático')
        st.markdown('#### Bling API')
        st.caption('Autentique o Bling primeiro. Depois escolha cadastro, estoque ou preços e envie no final pela API.')

        connected = bool(connection_status().get('connected'))
        if connected:
            st.success('Bling já conectado.')
            if st.button('Continuar via API', use_container_width=True, key='home_card_continue_bling_api'):
                _start_wizard_context('bling_api')
                st.rerun()
            return

        try:
            auth_url = build_authorization_url({'return_to': 'start', 'source_step': 'home_bling_api_card'})
        except Exception:
            auth_url = ''

        if auth_url:
            st.link_button('Conectar ao Bling', auth_url, use_container_width=True)
            st.caption('Após autorizar, você volta para escolher o tipo de envio da API.')
        else:
            st.warning('Credenciais do Bling ainda não configuradas. Use o modo CSV enquanto isso.')
            if st.button('Abrir etapa da API', use_container_width=True, key='home_card_open_bling_api_without_url'):
                _start_wizard_context('bling_api')
                st.rerun()


def _render_admin_links() -> None:
    with st.expander('Links úteis', expanded=False):
        st.caption('Atalhos do app e repositório. Área auxiliar, fora do fluxo principal.')
        if st.button('Abrir links do sistema', use_container_width=True, key='home_admin_open_system_links'):
            _set_flow(FLOW_LINKS_UTEIS)
            st.rerun()


def render_professional_home() -> None:
    add_audit_event(
        'home_router_render_professional_home',
        area='HOME',
        status='OK',
        details={
            'responsible_file': RESPONSIBLE_FILE,
            'home_order': 'bling_api_bling_csv_universal',
            'style': 'professional_light_cards',
        },
    )

    st.markdown('<div class="bling-home-section-title">Escolha como quer começar</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="bling-home-section-subtitle">Agora são três caminhos separados: API, CSV Bling ou Modelo Universal.</div>',
        unsafe_allow_html=True,
    )

    col_api, col_csv, col_universal = st.columns(3)
    with col_api:
        _render_bling_api_home_card()

    with col_csv:
        _render_home_card(
            'Bling CSV',
            'Use modelos oficiais do Bling para gerar CSV pronto para importação manual.',
            'Gerar CSV Bling',
            context='bling_csv',
            step=STEP_MODELO,
            key='home_card_open_bling_csv',
            badge='Importação manual',
        )

    with col_universal:
        _render_home_card(
            'Modelo Universal',
            'Use qualquer planilha final com cabeçalho próprio: marketplace, fornecedor ou layout personalizado.',
            'Iniciar Universal',
            context='universal',
            step=STEP_MODELO,
            key='home_card_open_universal',
            badge='Flexível',
        )

    st.markdown('<div class="bling-mini-note">A calculadora fica dentro da etapa Preço e também pode ser aberta pelo menu rápido.</div>', unsafe_allow_html=True)
    _render_admin_links()


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
            details={
                'responsible_file': RESPONSIBLE_FILE,
                'module_label': 'calculadora_principal',
                'quick_calculator_enabled': True,
                'legacy_direct_access': True,
            },
        )
        render_quick_price_calculator()
        st.markdown('---')
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
            details={'responsible_file': RESPONSIBLE_FILE, 'legacy_route': True},
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
            'single_page_flow_enabled': True,
            'home_entry_context': st.session_state.get(HOME_ENTRY_CONTEXT_KEY),
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
