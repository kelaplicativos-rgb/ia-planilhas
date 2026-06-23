from __future__ import annotations

import streamlit as st

from bling_app_zero.core.diagnostico_boot import boot_event, install_streamlit_boot_diagnostics
from bling_app_zero.core.universal_model_upload_fast_patch import install_universal_model_upload_fast_patch

install_streamlit_boot_diagnostics(st)
install_universal_model_upload_fast_patch()
boot_event(
    'app_boot_diagnostic_initialized_before_runtime_imports',
    area='BOOT',
    status='OK',
    details={'responsible_file': 'app.py', 'purpose': 'diagnostico nasce antes da Home, sidebar, wizard e fluxo Bling'},
)

from bling_app_zero.core import APP_VERSION, PAGE_CONFIG, register_critical_error
from bling_app_zero.core import bling_oauth
from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.brand_runtime_patch import install_brand_runtime_patch
from bling_app_zero.core.cache_control import clear_cache_once_per_version
from bling_app_zero.core.cache_schema_guard import enforce_cache_schema_guard, render_cache_schema_notice
from bling_app_zero.core.mapping_widget_state import restore_mapping_widget_state_from_snapshot
from bling_app_zero.core.official_bling_oauth_patch import install_official_bling_oauth_patch
from bling_app_zero.core.xml_nfe_runtime_patch import install_xml_nfe_runtime_patch
from bling_app_zero.ui.alerts import enforce_attention_alert_policy
from bling_app_zero.ui.bling_api_source_first_policy import install_bling_api_source_first_policy
from bling_app_zero.ui.bling_connected_entry_runtime import install_bling_connected_entry_runtime
from bling_app_zero.ui.blingfix_runtime_patches import install_blingfix_runtime_patches
from bling_app_zero.ui.home import render_home
from bling_app_zero.ui.layout import inject_streamlit_toolbar_fix
from bling_app_zero.ui.mapping_pagination_runtime import install_mapping_pagination_runtime
from bling_app_zero.ui.oauth_link_guard import install_oauth_link_guard
from bling_app_zero.ui.preventive_bootstrap import install_preventive_bootstrap
from bling_app_zero.ui.sidebar_tools import render_sidebar_tools
from bling_app_zero.ui.site_checkpoint_finalizer_runtime import install_site_checkpoint_finalizer_runtime
from bling_app_zero.ui.source_upload_recovery_runtime import install_source_upload_recovery_runtime
from bling_app_zero.ui.startup_guard import ensure_app_ready

RUNTIME_PATCH_KEYS_TO_REFRESH = ('blingfix_runtime_patches_installed_v7', 'blingfix_runtime_patches_installed_v8')
RUNTIME_PATCH_REFRESH_MARKER_KEY = 'blingfix_runtime_patch_refresh_marker_v1'
RUNTIME_PATCH_REFRESH_POLICY_VERSION = f'{APP_VERSION}:runtime_v10_api_source_first'
MOBILE_AUTO_ENTRY_KEY = 'mobile_connected_bling_auto_entry_done_v1'
DEVICE_HINT_KEY = 'app_device_hint_v1'
MOBILE_QUERY_VALUES = {'1', 'true', 'sim', 'yes', 'mobile', 'android', 'ios', 'phone', 'celular'}
DESKTOP_QUERY_VALUES = {'0', 'false', 'nao', 'não', 'no', 'desktop', 'wide'}


def _refresh_blingfix_runtime_patch_session() -> None:
    if st.session_state.get(RUNTIME_PATCH_REFRESH_MARKER_KEY) == RUNTIME_PATCH_REFRESH_POLICY_VERSION:
        return
    removed: list[str] = []
    for key in RUNTIME_PATCH_KEYS_TO_REFRESH:
        if key in st.session_state:
            st.session_state.pop(key, None)
            removed.append(key)
    st.session_state[RUNTIME_PATCH_REFRESH_MARKER_KEY] = RUNTIME_PATCH_REFRESH_POLICY_VERSION
    add_audit_event(
        'blingfix_runtime_patch_session_keys_refreshed_once_per_version',
        area='APP',
        status='OK' if removed else 'INFO',
        details={
            'removed_keys': removed,
            'policy_version': RUNTIME_PATCH_REFRESH_POLICY_VERSION,
            'reason': 'Atualizar runtime para fluxo API source-first sem reinstalar patches em todo rerun.',
            'responsible_file': 'app.py',
        },
    )


def _query_param(name: str) -> str:
    try:
        value = st.query_params.get(name)
    except Exception:
        return ''
    if isinstance(value, list):
        return str(value[0] if value else '').strip().lower()
    return str(value or '').strip().lower()


def _install_device_autodetect_css() -> None:
    st.markdown(
        '<style>@media (max-width:768px){[data-testid="stMainBlockContainer"],section.main>div{max-width:100vw!important;width:100%!important;padding-left:.62rem!important;padding-right:.62rem!important}.stButton>button,.stDownloadButton>button,a[data-testid="stLinkButton"]{min-height:48px!important;border-radius:14px!important;width:100%!important}}</style>',
        unsafe_allow_html=True,
    )


def _device_hint() -> str:
    query_hint = _query_param('device') or _query_param('layout') or _query_param('modo')
    if query_hint in MOBILE_QUERY_VALUES:
        st.session_state[DEVICE_HINT_KEY] = 'mobile'
        return 'mobile'
    if query_hint in DESKTOP_QUERY_VALUES:
        st.session_state[DEVICE_HINT_KEY] = 'desktop'
        return 'desktop'
    stored = str(st.session_state.get(DEVICE_HINT_KEY) or '').strip().lower()
    return stored if stored in {'mobile', 'desktop'} else 'auto'


def _auto_enter_wizard_when_bling_connected_on_mobile() -> None:
    if st.session_state.get(MOBILE_AUTO_ENTRY_KEY):
        return
    st.session_state[MOBILE_AUTO_ENTRY_KEY] = True
    add_audit_event(
        'app_mobile_connected_bling_auto_entry_disabled_for_dual_home',
        area='HOME',
        status='OK',
        details={'reason': 'Home deve permanecer visível para escolha de Mapear Planilha ou Bling.', 'device_hint': _device_hint(), 'responsible_file': 'app.py'},
    )


def _install_bling_api_verified_media_checkpoint(stage: str = 'startup') -> None:
    try:
        from bling_app_zero.core.existing_product_media_patch_runtime import install_existing_product_media_patch_runtime
        existing_installed = install_existing_product_media_patch_runtime()
    except Exception as exc:
        existing_installed = False
        add_audit_event('app_existing_product_media_patch_startup_failed', area='BLING_IMAGEM', status='AVISO', details={'error': str(exc)[:220], 'stage': stage, 'responsible_file': 'app.py'})
    try:
        from bling_app_zero.core.verified_image_checkpoint_runtime import install_verified_image_checkpoint_runtime
        installed = install_verified_image_checkpoint_runtime()
        add_audit_event('app_verified_media_checkpoint_startup', area='BLING_IMAGEM', status='OK', details={'installed_now': installed, 'existing_media_patch': existing_installed, 'stage': stage, 'responsible_file': 'app.py'})
    except Exception as exc:
        add_audit_event('app_verified_media_checkpoint_startup_failed', area='BLING_IMAGEM', status='AVISO', details={'error': str(exc)[:220], 'stage': stage, 'responsible_file': 'app.py'})


def main() -> None:
    st.set_page_config(**PAGE_CONFIG)
    _install_device_autodetect_css()
    enforce_attention_alert_policy()
    inject_streamlit_toolbar_fix()
    clear_cache_once_per_version(APP_VERSION)
    enforce_cache_schema_guard(APP_VERSION)

    if not ensure_app_ready():
        return

    install_preventive_bootstrap()
    restore_mapping_widget_state_from_snapshot()
    _install_bling_api_verified_media_checkpoint('before_runtime_patches')
    _refresh_blingfix_runtime_patch_session()
    install_blingfix_runtime_patches()
    install_site_checkpoint_finalizer_runtime()
    install_brand_runtime_patch()
    install_xml_nfe_runtime_patch()
    install_bling_api_source_first_policy()
    install_bling_connected_entry_runtime()
    install_source_upload_recovery_runtime()
    install_mapping_pagination_runtime()
    install_oauth_link_guard()
    _install_bling_api_verified_media_checkpoint('after_runtime_patches')
    install_official_bling_oauth_patch()
    bling_oauth.process_oauth_callback()
    _auto_enter_wizard_when_bling_connected_on_mobile()
    render_cache_schema_notice()
    add_audit_event('app_started', area='APP', details={'version': APP_VERSION, 'mode': 'session_guarded_start', 'device_hint': _device_hint()})

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
