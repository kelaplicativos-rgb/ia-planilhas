from __future__ import annotations

from html import escape, unescape

import streamlit as st

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
from bling_app_zero.ui.home_wizard_rerun import safe_rerun, set_step_without_rerun
from bling_app_zero.ui.scroll_position import request_scroll_top

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
HOME_BOOT_LOCK_KEY = 'home_boot_landing_rendered_once'
HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
BLING_AUTH_READY_KEY = 'home_bling_auth_ready_url'
FLOW_HOME = 'home'
FLOW_WIZARD = 'wizard_cadastro_estoque'

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
        set_step_without_rerun(STEP_ORIGEM)
        return STEP_ORIGEM
    if query_step in VALID_SINGLE_PAGE_STEPS:
        set_step_without_rerun(query_step)
        return query_step
    step = str(st.session_state.get(WIZARD_STEP_KEY) or '').strip().lower()
    if step == 'gerar_estoque':
        set_step_without_rerun(STEP_ORIGEM)
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
        set_step_without_rerun(step or STEP_MODELO)
    elif step:
        set_step_without_rerun(step)
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


def _clean_oauth_url(url: str) -> str:
    return unescape(str(url or '').strip()).replace('&amp;', '&')


def _same_tab_link(label: str, url: str) -> None:
    raw_url = _clean_oauth_url(url)
    if not raw_url:
        return
    safe_url = escape(raw_url, quote=True)
    safe_label = escape(label, quote=False)
    st.markdown(
        f'''
<a href="{safe_url}" target="_self" style="display:block;text-align:center;text-decoration:none;border:1px solid #d0d5dd;border-radius:14px;padding:0.85rem 1rem;font-weight:800;color:#5f6b7a;background:#ffffff;">
  {safe_label}
</a>
''',
        unsafe_allow_html=True,
    )


def _request_bling_link(auth_url: str) -> None:
    st.session_state[BLING_AUTH_READY_KEY] = _clean_oauth_url(auth_url)
    add_audit_event(
        'home_router_bling_auth_link_requested',
        area='HOME',
        status='OK',
        details={'responsible_file': RESPONSIBLE_FILE, 'connection_mode': 'same_tab_html_link'},
    )
    st.rerun()


def _render_open_bling_link(url: str) -> None:
    raw_url = _clean_oauth_url(url)
    if not raw_url:
        return
    st.success('Link oficial do Bling pronto. Toque abaixo para abrir a autorização na mesma aba.')
    _same_tab_link('Abrir tela oficial do Bling', raw_url)


def _render_bling_connection(auth_url: str) -> None:
    url = _clean_oauth_url(auth_url)
    if not url:
        st.warning('Não consegui gerar a autorização do Bling agora.')
        return

    ready_url = _clean_oauth_url(st.session_state.get(BLING_AUTH_READY_KEY) or '')
    if ready_url:
        _render_open_bling_link(ready_url)
    else:
        if st.button('Conectar ao Bling', use_container_width=True, key='home_bling_prepare_link_button'):
            _request_bling_link(url)

    with st.expander('Problemas para abrir?', expanded=False):
        st.caption('Copie o link apenas se o botão não abrir no seu navegador.')
        st.text_area('Link alternativo de autenticação', value=ready_url or url, height=100, key='bling_auth_url_fallback_hidden')

    if st.button('Já autorizei no Bling / verificar conexão', use_container_width=True, key='home_bling_verify_connection'):
        if bool(connection_status().get('connected')):
            st.session_state.pop(BLING_AUTH_READY_KEY, None)
            _start_wizard_context(CONTEXT_BLING_API)
            safe_rerun('home_bling_verify_connected')
        else:
            st.warning('Ainda não detectei a conexão. Autorize na tela oficial do Bling e tente verificar novamente.')

    add_audit_event(
        'home_router_bling_connection_visible',
        area='HOME',
        status='OK',
        details={'responsible_file': RESPONSIBLE_FILE, 'connection_mode': 'same_tab_html_link_no_popup'},
    )


def _render_light_entry_home() -> None:
    connected = bool(connection_status().get('connected'))
    st.markdown('<div class="bling-home-section-title">Começar</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="bling-home-section-subtitle">Conecte ao Bling para enviar por API ou continue sem conectar.</div>',
        unsafe_allow_html=True,
    )

    with st.container(border=True):
        st.markdown('#### Conectar ao Bling')
        if connected:
            st.session_state.pop(BLING_AUTH_READY_KEY, None)
            st.success('Bling já conectado.')
            if st.button('Continuar com Bling conectado', use_container_width=True, key='home_light_continue_connected_bling'):
                _start_wizard_context(CONTEXT_BLING_API)
                safe_rerun('home_light_continue_connected_bling')
        else:
            st.caption('Você será levado para a tela oficial do Bling nesta mesma aba para autorizar o acesso.')
            try:
                auth_url = build_authorization_url({'return_to': 'start', 'source_step': 'home_same_tab_connection'})
            except Exception as exc:
                auth_url = ''
                add_audit_event(
                    'home_router_bling_auth_url_error',
                    area='HOME',
                    status='ERRO',
                    details={'error': str(exc), 'responsible_file': RESPONSIBLE_FILE},
                )
            if auth_url:
                _render_bling_connection(auth_url)
            else:
                st.warning('Credenciais do Bling ainda não configuradas. Você ainda pode continuar sem conectar.')

    with st.container(border=True):
        st.markdown('#### Continuar sem conectar')
        st.caption('Prepare dados e planilhas sem envio direto pela API.')
        if st.button('Continuar sem conectar', use_container_width=True, key='home_light_continue_without_bling'):
            _start_wizard_context(CONTEXT_UNIVERSAL, step=STEP_MODELO)
            safe_rerun('home_light_continue_without_bling', target_step=STEP_MODELO)

    add_audit_event(
        'home_router_render_light_entry_home',
        area='HOME',
        status='OK',
        details={
            'responsible_file': RESPONSIBLE_FILE,
            'connected': connected,
            'home_order': 'same_tab_bling_or_continue_without',
            'lazy_flow_entry': True,
        },
    )


def render_professional_home() -> None:
    add_audit_event(
        'home_router_render_professional_home',
        area='HOME',
        status='OK',
        details={
            'responsible_file': RESPONSIBLE_FILE,
            'home_order': 'same_tab_bling_or_continue_without',
            'style': 'clean_connection_entry_no_iframe',
            'bling_oauth_target': 'same_tab_html_link',
            'legacy_routes_removed': True,
            'lazy_flow_entry': True,
        },
    )
    _render_light_entry_home()


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
