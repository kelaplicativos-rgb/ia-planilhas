from __future__ import annotations

from html import escape

import streamlit as st
import streamlit.components.v1 as components

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_oauth import build_authorization_url, connection_status
from bling_app_zero.ui.flow_context import (
    CONTEXT_BLING_API,
    CONTEXT_BLING_CSV,
    CONTEXT_UNIVERSAL,
    activate_csv_finish_mode,
    clear_api_skip_flag,
    clear_finish_mode,
    set_entry_context,
)
from bling_app_zero.ui.home_wizard import render_home_wizard
from bling_app_zero.ui.scroll_position import request_scroll_top

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
HOME_BOOT_LOCK_KEY = 'home_boot_landing_rendered_once'
HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
FLOW_HOME = 'home'
FLOW_WIZARD = 'wizard_cadastro_estoque'

# Mantidos apenas para compatibilidade com imports antigos. O router não renderiza mais essas rotas.
FLOW_PRICE_UPDATE = 'price_multistore_v2'
FLOW_LINKS_UTEIS = 'links_uteis'
FLOW_MODELOS_BLING = 'modelos_bling'
LEGACY_DISABLED_FLOWS = {FLOW_PRICE_UPDATE, FLOW_LINKS_UTEIS, FLOW_MODELOS_BLING}

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

    normalized_context = CONTEXT_UNIVERSAL if context == CONTEXT_BLING_CSV else context
    set_entry_context(normalized_context)

    if normalized_context == CONTEXT_BLING_API:
        clear_finish_mode()
        clear_api_skip_flag()
        st.session_state.pop(WIZARD_STEP_KEY, None)
    elif normalized_context == CONTEXT_UNIVERSAL:
        activate_csv_finish_mode()
        st.session_state[WIZARD_STEP_KEY] = step or STEP_MODELO
    elif step:
        st.session_state[WIZARD_STEP_KEY] = step
    else:
        st.session_state.pop(WIZARD_STEP_KEY, None)

    if context == CONTEXT_BLING_CSV:
        add_audit_event(
            'home_router_bling_csv_legacy_redirected_to_universal',
            area='HOME',
            status='LEGADO_REDIRECIONADO',
            details={'responsible_file': RESPONSIBLE_FILE},
        )

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


def _render_home_card(
    title: str,
    subtitle: str,
    button: str,
    *,
    context: str | None = None,
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
            st.rerun()


def _render_same_tab_bling_link(auth_url: str) -> None:
    safe_url = escape(str(auth_url or ''), quote=True)
    if not safe_url:
        st.warning('Não consegui gerar o link de conexão com o Bling agora.')
        return

    components.html(
        f'''
<div style="width:100%; font-family:Arial, sans-serif;">
    <button
        type="button"
        onclick="
            const oauthUrl = '{safe_url}';
            const popup = window.open(
                oauthUrl,
                'bling_oauth_popup',
                'width=520,height=720,menubar=no,toolbar=no,location=yes,status=no,scrollbars=yes,resizable=yes'
            );

            if (!popup || popup.closed || typeof popup.closed === 'undefined') {{
                window.location.href = oauthUrl;
            }}
        "
        style="
            display:block;
            width:100%;
            box-sizing:border-box;
            text-align:center;
            font-weight:700;
            padding:0.65rem 1rem;
            border-radius:0.5rem;
            border:1px solid rgba(49,51,63,.2);
            color:#4b5563;
            background:#ffffff;
            cursor:pointer;
        "
    >
        Conectar ao Bling
    </button>
    <div style="margin-top:8px; font-size:12px; color:#6b7280; text-align:center;">
        Se o popup for bloqueado, o Bling será aberto na mesma aba.
    </div>
</div>
''',
        height=92,
    )


def _render_bling_api_home_card() -> None:
    with st.container(border=True):
        st.caption('Mais automático')
        st.markdown('#### Bling API')
        st.caption('Autentique o Bling primeiro. Depois escolha cadastro, estoque ou preços e envie no final pela API.')

        connected = bool(connection_status().get('connected'))
        if connected:
            st.success('Bling já conectado.')
            if st.button('Continuar via API', use_container_width=True, key='home_card_continue_bling_api'):
                _start_wizard_context(CONTEXT_BLING_API)
                st.rerun()
            return

        try:
            auth_url = build_authorization_url({'return_to': 'start', 'source_step': 'home_bling_api_card'})
        except Exception:
            auth_url = ''

        if auth_url:
            _render_same_tab_bling_link(auth_url)
            st.caption('Após autorizar, você volta para escolher o tipo de envio da API.')
        else:
            st.warning('Credenciais do Bling ainda não configuradas. Use o Modelo Universal enquanto isso.')
            if st.button('Abrir etapa da API', use_container_width=True, key='home_card_open_bling_api_without_url'):
                _start_wizard_context(CONTEXT_BLING_API)
                st.rerun()


def render_professional_home() -> None:
    add_audit_event(
        'home_router_render_professional_home',
        area='HOME',
        status='OK',
        details={
            'responsible_file': RESPONSIBLE_FILE,
            'home_order': 'bling_api_universal',
            'style': 'professional_light_cards',
            'bling_oauth_target': 'popup_with_same_tab_fallback',
            'legacy_routes_removed': True,
            'bling_csv_legacy_redirected_to_universal': True,
        },
    )

    st.markdown('<div class="bling-home-section-title">Escolha como quer começar</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="bling-home-section-subtitle">Agora são dois caminhos: envio direto pela API ou Modelo Universal.</div>',
        unsafe_allow_html=True,
    )

    col_api, col_universal = st.columns(2)
    with col_api:
        _render_bling_api_home_card()

    with col_universal:
        _render_home_card(
            'Modelo Universal',
            'Use qualquer planilha final com cabeçalho próprio: marketplace, fornecedor ou layout personalizado.',
            'Iniciar Universal',
            context=CONTEXT_UNIVERSAL,
            step=STEP_MODELO,
            key='home_card_open_universal',
            badge='Flexível',
        )


def _redirect_legacy_flow_to_home(flow: str) -> None:
    add_audit_event(
        'home_router_legacy_flow_removed',
        area='HOME',
        status='LEGADO_REDIRECIONADO',
        details={'legacy_flow': flow, 'responsible_file': RESPONSIBLE_FILE},
    )
    _set_home_flow()
    render_professional_home()


def render_home_router() -> None:
    requested_flow = _requested_flow()

    if requested_flow in {'', FLOW_HOME}:
        _set_home_flow()
        render_professional_home()
        return

    if requested_flow in LEGACY_DISABLED_FLOWS:
        _redirect_legacy_flow_to_home(requested_flow)
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
