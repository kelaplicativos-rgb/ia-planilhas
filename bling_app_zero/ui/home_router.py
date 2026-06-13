from __future__ import annotations

from html import escape, unescape

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_oauth import build_authorization_url, connection_status
from bling_app_zero.ui.bling_backend_bridge import backend_connection_status, sync_backend_token_to_streamlit
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
HOME_FLOW_SCHEMA_KEY = 'home_source_first_flow_schema_v1'
HOME_FLOW_SCHEMA_VERSION = 'source_first_origin_start_v4_unified_bling_20260613'
BLING_AUTH_READY_KEY = 'home_bling_auth_ready_url'
BLING_BACKEND_LAST_STATUS_KEY = 'home_bling_backend_last_status'
UNIFIED_BLING_SEND_KEY = 'home_bling_connected_same_flow_api_send'
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

STALE_FLOW_KEYS = (
    ACTIVE_FLOW_KEY,
    HOME_ALLOW_FLOW_KEY,
    HOME_BOOT_LOCK_KEY,
    HOME_ENTRY_CONTEXT_KEY,
    WIZARD_STEP_KEY,
    UNIFIED_BLING_SEND_KEY,
    'home_single_page_flow_active',
    'home_slim_flow_origin',
    'home_slim_flow_operation',
    'home_detected_operation',
    'frontpage_origin_radio_universal',
    'origem_final',
    'origem_dados',
    'origem_tipo',
    'origem_planilha_via_site',
    'site_gerou_origem_planilha',
    'operation_site',
    'tipo_operacao_site',
    'tipo_operacao',
    'operacao_final',
    'tipo_operacao_final',
    'active_feature_contract_key',
    'active_feature_operation',
    'active_feature_mode',
    'flow_spine_operation',
    'flow_spine_final_destination',
    'flow_spine_sender_operation',
    'flow_spine_api_batch_operation',
    'site_capture_running',
    'site_capture_finished',
    'site_capture_result_ready',
    'site_capture_error',
    'site_capture_rows',
    'site_capture_columns',
    'site_capture_operation',
    'site_capture_started_at',
    'blingsmartscan_manual_continue_required',
    'blingsmartscan_ready_to_continue',
    'blingsmartscan_continue_target_step',
    'blingsmartscan_finished_operation',
    'blingsmartscan_finished_rows',
    'blingsmartscan_finished_columns',
)
STALE_FLOW_PREFIXES = (
    'df_site_bruto',
    'df_origem_site_como_planilha_',
    'site_source_urls_como_planilha_',
    'site_requested_columns_como_planilha_',
    'site_deep_capture_',
    'blingsmartscan_notice_',
    'blingsmartscan_decision_',
    'blingsmartscan_report_',
)


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


def _reset_stale_flow_session_if_needed() -> None:
    """Força sessão antiga a voltar para a primeira tela correta após deploy.

    O Streamlit preserva session_state entre reruns. Depois da mudança para
    fluxo Origem -> Entrada -> Modelo, sessões antigas podem continuar abrindo
    direto em Entrada/Site/Estoque ou no painel curto de Bling conectado.
    """
    if st.session_state.get(HOME_FLOW_SCHEMA_KEY) == HOME_FLOW_SCHEMA_VERSION:
        return

    removed: list[str] = []
    for key in STALE_FLOW_KEYS:
        if key in st.session_state:
            st.session_state.pop(key, None)
            removed.append(key)
    for key in list(st.session_state.keys()):
        text_key = str(key)
        if any(text_key.startswith(prefix) for prefix in STALE_FLOW_PREFIXES):
            st.session_state.pop(key, None)
            removed.append(text_key)

    st.session_state[HOME_FLOW_SCHEMA_KEY] = HOME_FLOW_SCHEMA_VERSION
    _clear_navigation_params()
    add_audit_event(
        'home_router_source_first_schema_session_reset',
        area='HOME',
        status='OK',
        details={
            'responsible_file': RESPONSIBLE_FILE,
            'schema_version': HOME_FLOW_SCHEMA_VERSION,
            'removed_count': len(removed),
            'removed_keys': removed[:80],
            'reason': 'force_home_after_unified_bling_flow_deploy',
        },
    )


def _set_home_flow() -> None:
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_HOME
    st.session_state[HOME_ALLOW_FLOW_KEY] = False
    st.session_state['home_single_page_flow_active'] = False
    st.session_state.pop(HOME_ENTRY_CONTEXT_KEY, None)
    st.session_state.pop(UNIFIED_BLING_SEND_KEY, None)
    _clear_navigation_params()


def _enable_unified_bling_send(enabled: bool) -> None:
    if enabled:
        st.session_state[UNIFIED_BLING_SEND_KEY] = True
    else:
        st.session_state.pop(UNIFIED_BLING_SEND_KEY, None)


def _start_wizard_context(context: str, *, step: str | None = None, api_send: bool = False) -> None:
    request_scroll_top()
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_WIZARD
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    st.session_state['home_single_page_flow_active'] = True

    # BLINGFIX 2026-06-13:
    # Bling conectado não pode abrir outro dashboard/fluxo curto.
    # Ele entra no MESMO fluxo universal e apenas marca o destino final como envio API.
    connected_bling_flow = bool(api_send or context == CONTEXT_BLING_API)
    normalized_context = CONTEXT_UNIVERSAL if context in {CONTEXT_BLING_CSV, CONTEXT_BLING_API} else context
    set_entry_context(normalized_context)

    if normalized_context == CONTEXT_UNIVERSAL:
        activate_csv_finish_mode()
        if connected_bling_flow:
            clear_api_skip_flag()
        _enable_unified_bling_send(connected_bling_flow)
        set_step_without_rerun(step or STEP_ORIGEM)
    elif step:
        _enable_unified_bling_send(False)
        set_step_without_rerun(step)
    else:
        _enable_unified_bling_send(False)
        clear_finish_mode()
        st.session_state.pop(WIZARD_STEP_KEY, None)

    if context == CONTEXT_BLING_CSV:
        add_audit_event(
            'home_router_bling_csv_legacy_redirected_to_universal',
            area='HOME',
            status='LEGADO_REDIRECIONADO',
            details={'responsible_file': RESPONSIBLE_FILE},
        )
    if connected_bling_flow:
        add_audit_event(
            'home_router_bling_api_redirected_to_unified_flow',
            area='HOME',
            status='OK',
            details={'responsible_file': RESPONSIBLE_FILE, 'step': step or STEP_ORIGEM},
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


def _android_safe_oauth_links(label: str, url: str) -> None:
    raw_url = _clean_oauth_url(url)
    if not raw_url:
        return
    safe_url = escape(raw_url, quote=True)
    safe_label = escape(label, quote=False)
    st.info('No Android, alguns navegadores internos podem abrir uma tela vazia. Se a primeira opção falhar, use a opção de compatibilidade ou copie o link.')
    try:
        st.link_button(safe_label, raw_url, use_container_width=True)
    except Exception:
        pass
    st.markdown(
        f'''
<a href="{safe_url}" target="_top" style="display:block;text-align:center;text-decoration:none;border:1px solid #2563eb;border-radius:14px;padding:0.85rem 1rem;font-weight:900;color:#ffffff;background:#2563eb;box-shadow:0 10px 22px rgba(37,99,235,.18);">
  Abrir conexão nesta aba se o Android bloquear
</a>
''',
        unsafe_allow_html=True,
    )


def _same_tab_link(label: str, url: str) -> None:
    # Compatibilidade: o antigo same_tab agora usa fallback Android seguro.
    _android_safe_oauth_links(label, url)


def _request_bling_link(auth_url: str) -> None:
    st.session_state[BLING_AUTH_READY_KEY] = _clean_oauth_url(auth_url)
    add_audit_event(
        'home_router_bling_auth_link_requested',
        area='HOME',
        status='OK',
        details={'responsible_file': RESPONSIBLE_FILE, 'connection_mode': 'android_safe_oauth_link'},
    )
    st.rerun()


def _render_open_bling_link(url: str) -> None:
    raw_url = _clean_oauth_url(url)
    if not raw_url:
        return
    st.success('Link oficial do Bling pronto. Toque abaixo para abrir a autorização.')
    _android_safe_oauth_links('Abrir tela oficial do Bling', raw_url)


def _safe_backend_status() -> dict:
    try:
        status = backend_connection_status()
        return status if isinstance(status, dict) else {'enabled': False, 'connected': False}
    except Exception as exc:
        return {'enabled': True, 'connected': False, 'error': str(exc)[:220], 'source': 'backend'}


def _effective_bling_status(*, try_sync: bool = True) -> dict:
    local_status = connection_status()
    if bool(local_status.get('connected')):
        return {'connected': True, 'local_connected': True, 'backend_connected': False, 'status': local_status, 'backend_status': {}}

    backend_status = _safe_backend_status()
    st.session_state[BLING_BACKEND_LAST_STATUS_KEY] = backend_status
    backend_connected = bool(backend_status.get('connected'))
    synced = False
    if backend_connected and try_sync:
        synced = bool(sync_backend_token_to_streamlit())
        local_status = connection_status()
        if bool(local_status.get('connected')):
            add_audit_event(
                'home_router_bling_backend_status_synced',
                area='HOME',
                status='OK',
                details={'responsible_file': RESPONSIBLE_FILE, 'backend_connected': True, 'token_synced': True},
            )
            return {'connected': True, 'local_connected': True, 'backend_connected': True, 'token_synced': True, 'status': local_status, 'backend_status': backend_status}

    return {
        'connected': False,
        'local_connected': False,
        'backend_connected': backend_connected,
        'token_synced': synced,
        'status': local_status,
        'backend_status': backend_status,
    }


def _render_backend_oauth_warning(effective_status: dict) -> None:
    backend_status = effective_status.get('backend_status') if isinstance(effective_status.get('backend_status'), dict) else {}
    local_status = effective_status.get('status') if isinstance(effective_status.get('status'), dict) else {}
    if bool(effective_status.get('backend_connected')) and not bool(effective_status.get('connected')):
        st.warning(
            'O Bling autorizou no backend, mas o Streamlit ainda não conseguiu importar o token. '
            'Confira o segredo compartilhado BLING_BACKEND_SHARED_SECRET no Streamlit e no backend Render.'
        )
    elif bool(backend_status.get('enabled')) and backend_status.get('error'):
        st.warning(f'Backend OAuth encontrado, mas não respondeu corretamente ao status: {backend_status.get("error")}')
    elif bool(backend_status.get('enabled')) and not bool(backend_status.get('connected')):
        st.warning('Ainda não detectei callback/token salvo no backend. Autorize no Bling e depois toque em verificar conexão.')
    else:
        message = str(local_status.get('message') or 'Bling ainda não conectado.')
        st.warning(message)

    with st.expander('Diagnóstico da conexão Bling', expanded=False):
        st.write(
            {
                'connected_local_streamlit': bool(local_status.get('connected')),
                'connected_backend_render': bool(backend_status.get('connected')),
                'backend_enabled': bool(backend_status.get('enabled')),
                'backend_error': backend_status.get('error', ''),
                'backend_saved_at': backend_status.get('saved_at', ''),
                'backend_expires_at': backend_status.get('expires_at', ''),
                'required_redirect_uri': local_status.get('required_redirect_uri'),
                'token_bridge_ready': backend_status.get('token_bridge_ready'),
                'responsible_file': RESPONSIBLE_FILE,
            }
        )


def _render_bling_connection(auth_url: str) -> None:
    url = _clean_oauth_url(auth_url)
    if not url:
        st.warning('Não consegui gerar a autorização do Bling agora.')
        return

    ready_url = _clean_oauth_url(st.session_state.get(BLING_AUTH_READY_KEY) or '')
    if ready_url:
        _render_open_bling_link(ready_url)
    else:
        if st.button('Preparar conexão com o Bling', use_container_width=True, key='home_bling_prepare_link_button'):
            _request_bling_link(url)

    with st.expander('Problemas para abrir?', expanded=False):
        st.caption('Copie o link apenas se os botões não abrirem no seu navegador.')
        st.text_area('Link alternativo de autenticação', value=ready_url or url, height=100, key='bling_auth_url_fallback_hidden')

    if st.button('Já autorizei no Bling / verificar conexão', use_container_width=True, key='home_bling_verify_connection'):
        effective_status = _effective_bling_status(try_sync=True)
        if bool(effective_status.get('connected')):
            st.session_state.pop(BLING_AUTH_READY_KEY, None)
            _start_wizard_context(CONTEXT_BLING_API, step=STEP_ORIGEM, api_send=True)
            safe_rerun('home_bling_verify_connected')
        else:
            add_audit_event(
                'home_router_bling_verify_connection_failed',
                area='HOME',
                status='AVISO',
                details={
                    'responsible_file': RESPONSIBLE_FILE,
                    'backend_connected': bool(effective_status.get('backend_connected')),
                    'local_connected': bool(effective_status.get('local_connected')),
                    'token_synced': bool(effective_status.get('token_synced')),
                },
            )
            _render_backend_oauth_warning(effective_status)

    add_audit_event(
        'home_router_bling_connection_visible',
        area='HOME',
        status='OK',
        details={'responsible_file': RESPONSIBLE_FILE, 'connection_mode': 'android_safe_oauth_link'},
    )


def _render_light_entry_home() -> None:
    effective_status = _effective_bling_status(try_sync=True)
    connected = bool(effective_status.get('connected'))
    st.markdown('<div class="bling-home-section-title">Começar</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="bling-home-section-subtitle">Use o mesmo fluxo sempre. Se o Bling estiver conectado, o envio aparece somente no final.</div>',
        unsafe_allow_html=True,
    )

    if connected:
        st.success('Bling conectado. O fluxo continua igual; no final você poderá enviar ao Bling ou baixar o backup.')
        col_api, col_file = st.columns(2)
        with col_api:
            if st.button('Usar Bling conectado', use_container_width=True, key='home_use_connected_bling'):
                _start_wizard_context(CONTEXT_BLING_API, step=STEP_ORIGEM, api_send=True)
                safe_rerun('home_use_connected_bling_unified')
        with col_file:
            if st.button('Gerar arquivo sem API', use_container_width=True, key='home_continue_without_bling_connected'):
                _start_wizard_context(CONTEXT_UNIVERSAL, step=STEP_ORIGEM, api_send=False)
                safe_rerun('home_continue_without_bling_connected')
        return

    try:
        auth_url = build_authorization_url({'return_to': 'home_light_entry', 'open_mode': 'android_safe'})
    except Exception as exc:
        auth_url = ''
        st.warning(f'Não consegui preparar o link do Bling agora: {exc}')

    _render_bling_connection(auth_url)

    st.divider()
    if st.button('Continuar sem conectar ao Bling', use_container_width=True, key='home_continue_without_bling'):
        _start_wizard_context(CONTEXT_UNIVERSAL, step=STEP_ORIGEM, api_send=False)
        safe_rerun('home_continue_without_bling')

    add_audit_event(
        'home_router_render_light_entry_home',
        area='HOME',
        status='OK',
        details={
            'responsible_file': RESPONSIBLE_FILE,
            'connected': connected,
            'backend_connected': bool(effective_status.get('backend_connected')),
            'local_connected': bool(effective_status.get('local_connected')),
            'home_order': 'same_flow_bling_connected_or_csv',
            'lazy_flow_entry': True,
            'csv_first_step': STEP_ORIGEM,
            'schema_version': HOME_FLOW_SCHEMA_VERSION,
        },
    )


def _render_professional_home() -> None:
    st.markdown(
        '''
<style>
.bling-home-hero{border:1px solid rgba(15,23,42,.10);background:linear-gradient(135deg,#ffffff 0%,#f8fafc 100%);border-radius:22px;padding:1.05rem 1rem;margin:.35rem 0 1rem 0;box-shadow:0 14px 34px rgba(15,23,42,.06)}
.bling-home-eyebrow{font-size:.78rem;font-weight:800;color:#2563eb;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.35rem}.bling-home-title{font-size:1.55rem;line-height:1.08;font-weight:950;color:#0f172a;margin:0}.bling-home-subtitle{font-size:.95rem;line-height:1.38;color:#475569;margin:.65rem 0 0 0}.bling-home-section-title{font-size:1.05rem;font-weight:900;color:#0f172a;margin:1rem 0 .25rem}.bling-home-section-subtitle{font-size:.88rem;color:#64748b;margin:0 0 .75rem}.bling-home-card{border:1px solid rgba(15,23,42,.08);background:#fff;border-radius:18px;padding:.95rem;margin:.65rem 0}.bling-home-alert{border:1px solid rgba(234,88,12,.30);background:rgba(255,237,213,.75);color:#7c2d12;border-radius:16px;padding:.85rem .9rem;font-weight:700;line-height:1.35}.bling-home-muted{font-size:.82rem;color:#64748b;line-height:1.35}
</style>
<div class="bling-home-hero">
  <div class="bling-home-eyebrow">MapeiaAI · Bling</div>
  <h1 class="bling-home-title">Mapeie uma vez. Envie ao Bling ou baixe o arquivo.</h1>
  <p class="bling-home-subtitle">Fluxo único: origem, dados, modelo, mapeamento, prévia final e saída. Conectar ao Bling não muda a dashboard.</p>
</div>
''',
        unsafe_allow_html=True,
    )
    _render_light_entry_home()
    add_audit_event(
        'home_router_render_professional_home',
        area='HOME',
        status='OK',
        details={
            'responsible_file': RESPONSIBLE_FILE,
            'home_order': 'same_flow_bling_connected_or_csv',
            'style': 'clean_connection_entry_no_iframe',
            'bling_oauth_target': 'android_safe_top_or_copy',
            'legacy_routes_removed': True,
            'lazy_flow_entry': True,
            'csv_first_step': STEP_ORIGEM,
            'schema_version': HOME_FLOW_SCHEMA_VERSION,
        },
    )


def render_home() -> None:
    _reset_stale_flow_session_if_needed()
    flow = _requested_flow()
    if flow == FLOW_HOME:
        _render_professional_home()
        return
    if flow == FLOW_WIZARD:
        _set_single_page_wizard_state()
        render_home_wizard()
        return
    if flow in LEGACY_DISABLED_FLOWS:
        _set_home_flow()
        safe_rerun('legacy_home_flow_disabled')
        return
    _set_home_flow()
    _render_professional_home()


__all__ = ['render_home']
