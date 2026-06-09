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
from bling_app_zero.ui.preventive_bootstrap import install_preventive_bootstrap
from bling_app_zero.ui.sidebar_tools import render_sidebar_tools
from bling_app_zero.ui.startup_guard import ensure_app_ready


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
    install_blingfix_runtime_patches()
    _install_bling_api_verified_media_checkpoint('after_runtime_patches')
    bling_oauth.process_oauth_callback()
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
