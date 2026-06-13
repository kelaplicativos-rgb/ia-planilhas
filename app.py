from __future__ import annotations

import streamlit as st

from bling_app_zero.core import APP_VERSION, PAGE_CONFIG, register_critical_error
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core import bling_oauth
from bling_app_zero.core.cache_control import clear_cache_once_per_version
from bling_app_zero.core.mapping_widget_state import restore_mapping_widget_state_from_snapshot
from bling_app_zero.ui.alerts import enforce_attention_alert_policy
from bling_app_zero.ui.blingfix_runtime_patches import install_blingfix_runtime_patches
from bling_app_zero.ui.home import render_home
from bling_app_zero.ui.layout import inject_streamlit_toolbar_fix
from bling_app_zero.ui.oauth_link_guard import install_oauth_link_guard
from bling_app_zero.ui.preventive_bootstrap import install_preventive_bootstrap
from bling_app_zero.ui.sidebar_tools import render_sidebar_tools
from bling_app_zero.ui.startup_guard import ensure_app_ready


RUNTIME_PATCH_KEYS_TO_REFRESH = (
    'blingfix_runtime_patches_installed_v7',
    'blingfix_runtime_patches_installed_v8',
)

MOBILE_AUTO_ENTRY_KEY = 'mobile_connected_bling_auto_entry_done_v1'
FLOW_WIZARD = 'wizard_cadastro_estoque'
STEP_ORIGEM = 'origem'
HOME_SCHEMA_KEY = 'home_source_first_flow_schema_v1'
HOME_SCHEMA_VERSION = 'source_first_origin_start_v4_unified_bling_20260613'


def _refresh_blingfix_runtime_patch_session() -> None:
    removed: list[str] = []
    for key in RUNTIME_PATCH_KEYS_TO_REFRESH:
        if key in st.session_state:
            st.session_state.pop(key, None)
            removed.append(key)
    if removed:
        add_audit_event(
            'blingfix_runtime_patch_session_keys_refreshed',
            area='APP',
            status='OK',
            details={
                'removed_keys': removed,
                'reason': 'Forçar instalação do runtime atualizado de busca única API/site.',
                'responsible_file': 'app.py',
            },
        )


def _auto_enter_mobile_wizard_when_bling_connected() -> None:
    """Evita parar na landing quando o Bling já está conectado.

    A landing com os botões "Usar Bling conectado" e "Gerar arquivo sem API" é útil
    só antes da escolha. Depois da conexão, no celular, o esperado é abrir direto
    o fluxo mobile normal e deixar o envio ao Bling apenas para o final.
    """
    if st.session_state.get(MOBILE_AUTO_ENTRY_KEY):
        return
    if str(st.session_state.get('home_active_operation_v2') or '') == FLOW_WIZARD:
        return
    try:
        connected = bool(bling_oauth.connection_status().get('connected'))
    except Exception:
        connected = False
    if not connected:
        return

    st.session_state[MOBILE_AUTO_ENTRY_KEY] = True
    st.session_state['home_active_operation_v2'] = FLOW_WIZARD
    st.session_state['home_allow_operation_v2_session'] = True
    st.session_state['home_single_page_flow_active'] = True
    st.session_state['home_boot_landing_rendered_once'] = True
    st.session_state['home_entry_context'] = 'universal'
    st.session_state['home_slim_entry_context'] = 'universal'
    st.session_state['bling_finish_mode'] = 'csv_download'
    st.session_state['finish_mode'] = 'csv_download'
    st.session_state['home_bling_connected_same_flow_api_send'] = True
    st.session_state['bling_wizard_step'] = STEP_ORIGEM
    st.session_state['home_wizard_step'] = STEP_ORIGEM
    st.session_state[HOME_SCHEMA_KEY] = HOME_SCHEMA_VERSION
    st.session_state.pop('home_bling_auth_ready_url', None)
    try:
        st.query_params['operation_v2'] = FLOW_WIZARD
        st.query_params['step'] = STEP_ORIGEM
        for key in ('flow', 'origem', 'operacao', 'operation'):
            st.query_params.pop(key, None)
    except Exception:
        pass

    add_audit_event(
        'app_mobile_connected_bling_auto_entered_wizard',
        area='HOME',
        status='OK',
        details={
            'reason': 'Bling conectado; abrir fluxo mobile normal em vez da landing.',
            'target_flow': FLOW_WIZARD,
            'target_step': STEP_ORIGEM,
            'api_send_flag': True,
            'responsible_file': 'app.py',
        },
    )


def _install_bling_api_verified_media_checkpoint(stage: str = 'startup') -> None:
    try:
        from bling_app_zero.core.existing_product_media_patch_runtime import install_existing_product_media_patch_runtime
        existing_installed = install_existing_product_media_patch_runtime()
    except Exception as exc:
        existing_installed = False
        add_audit_event(
            'app_existing_product_media_patch_startup_failed',
            area='BLING_IMAGEM',
            status='AVISO',
            details={'error': str(exc)[:220], 'stage': stage, 'responsible_file': 'app.py'},
        )
    try:
        from bling_app_zero.core.verified_image_checkpoint_runtime import install_verified_image_checkpoint_runtime
        installed = install_verified_image_checkpoint_runtime()
        add_audit_event(
            'app_verified_media_checkpoint_startup',
            area='BLING_IMAGEM',
            status='OK',
            details={'installed_now': installed, 'existing_media_patch': existing_installed, 'stage': stage, 'responsible_file': 'app.py'},
        )
    except Exception as exc:
        add_audit_event(
            'app_verified_media_checkpoint_startup_failed',
            area='BLING_IMAGEM',
            status='AVISO',
            details={'error': str(exc)[:220], 'stage': stage, 'responsible_file': 'app.py'},
        )


def main() -> None:
    st.set_page_config(**PAGE_CONFIG)
    enforce_attention_alert_policy()
    inject_streamlit_toolbar_fix()
    clear_cache_once_per_version(APP_VERSION)

    if not ensure_app_ready():
        return

    install_preventive_bootstrap()
    restore_mapping_widget_state_from_snapshot()
    _install_bling_api_verified_media_checkpoint('before_runtime_patches')
    _refresh_blingfix_runtime_patch_session()
    install_blingfix_runtime_patches()
    install_oauth_link_guard()
    _install_bling_api_verified_media_checkpoint('after_runtime_patches')
    bling_oauth.process_oauth_callback()
    _auto_enter_mobile_wizard_when_bling_connected()
    add_audit_event('app_started', area='APP', details={'version': APP_VERSION, 'mode': 'session_guarded_start'})

    try:
        render_sidebar_tools()
        add_audit_event('sidebar_rendered_before_home', area='APP')
    except Exception as exc:
        formatted_sidebar = register_critical_error(exc)
        add_audit_event('sidebar_critical_error', area='APP', status='ERRO', details={'error': str(exc)})
        st.warning('O painel lateral não carregou, mas o sistema principal continuará aberto.')
        with st.expander('Ver erro do painel lateral', expanded=False):
            st.code(formatted_sidebar)

    try:
        render_home()
        add_audit_event('home_rendered', area='APP')
    except Exception as exc:
        formatted = register_critical_error(exc)
        add_audit_event('app_critical_error', area='APP', status='ERRO', details={'error': str(exc)})
        st.error('Encontrei um erro interno, mas o aplicativo continuou aberto.')
        st.caption('Abra Admin / Diagnóstico com a chave de suporte para gerar o arquivo técnico do próximo BLINGFIX.')
        with st.expander('Ver detalhe técnico do erro', expanded=False):
            st.code(formatted)


if __name__ == '__main__':
    main()
