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
from bling_app_zero.ui.mapping_pagination_runtime import install_mapping_pagination_runtime
from bling_app_zero.ui.oauth_link_guard import install_oauth_link_guard
from bling_app_zero.ui.preventive_bootstrap import install_preventive_bootstrap
from bling_app_zero.ui.sidebar_tools import render_sidebar_tools
from bling_app_zero.ui.startup_guard import ensure_app_ready


RUNTIME_PATCH_KEYS_TO_REFRESH = (
    'blingfix_runtime_patches_installed_v7',
    'blingfix_runtime_patches_installed_v8',
)
RUNTIME_PATCH_REFRESH_MARKER_KEY = 'blingfix_runtime_patch_refresh_marker_v1'
RUNTIME_PATCH_REFRESH_POLICY_VERSION = f'{APP_VERSION}:runtime_v9_flow_stability'

MOBILE_AUTO_ENTRY_KEY = 'mobile_connected_bling_auto_entry_done_v1'
DEVICE_HINT_KEY = 'app_device_hint_v1'
FLOW_WIZARD = 'wizard_cadastro_estoque'
STEP_ORIGEM = 'origem'
HOME_SCHEMA_KEY = 'home_source_first_flow_schema_v1'
HOME_SCHEMA_VERSION = 'source_first_origin_start_v4_unified_bling_20260613'
MOBILE_QUERY_VALUES = {'1', 'true', 'sim', 'yes', 'mobile', 'android', 'ios', 'phone', 'celular'}
DESKTOP_QUERY_VALUES = {'0', 'false', 'nao', 'não', 'no', 'desktop', 'wide'}


def _refresh_blingfix_runtime_patch_session() -> None:
    """Atualiza patches runtime no máximo uma vez por versão/política.

    Antes este bloco removia as chaves de patch em todo rerun do Streamlit.
    Isso fazia os patches serem reinstalados várias vezes na mesma sessão e
    gerava instabilidade perceptível na Home, sidebar e fluxos.
    """
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
            'reason': 'Evitar reinstalação destrutiva de patches a cada rerun; refresh permitido apenas quando a política/versão muda.',
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
        '''
<style>
:root{--mapeia-device-mode:desktop;}
[data-testid="stAppViewContainer"] .main .block-container{max-width:1180px;}
@media (max-width: 768px), (pointer: coarse) and (max-width: 980px){
  :root{--mapeia-device-mode:mobile;}
  [data-testid="stAppViewContainer"] .main .block-container,
  [data-testid="stMainBlockContainer"],
  section.main > div{
    max-width: 100vw !important;
    width: 100% !important;
    padding-left: .62rem !important;
    padding-right: .62rem !important;
  }
  div[data-testid="column"]{width:100% !important; flex: 1 1 100% !important; min-width:100% !important;}
  div[data-testid="stHorizontalBlock"]{gap:.6rem !important; flex-wrap:wrap !important;}
  .stButton > button, .stDownloadButton > button, a[data-testid="stLinkButton"]{min-height:48px !important; border-radius:14px !important; width:100% !important;}
  h1{font-size:1.55rem !important; line-height:1.12 !important;}
  h2{font-size:1.35rem !important; line-height:1.18 !important;}
  h3{font-size:1.08rem !important; line-height:1.22 !important;}
}
</style>
''',
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
    if stored in {'mobile', 'desktop'}:
        return stored
    return 'auto'


def _should_skip_connected_landing_for_current_device() -> bool:
    hint = _device_hint()
    if hint == 'desktop':
        return False
    if hint == 'mobile':
        return False
    open_mode = _query_param('open_mode')
    if open_mode in {'android_safe', 'mobile'}:
        st.session_state[DEVICE_HINT_KEY] = 'mobile'
        return False
    return False


def _auto_enter_wizard_when_bling_connected_on_mobile() -> None:
    # BLINGFIX 2026-06-22:
    # A Home é o núcleo de decisão do MapeiaAI. Mesmo no celular e mesmo com
    # Bling já conectado, o usuário precisa ver os dois botões principais:
    # Anexar Modelo / Mapear e Conectar/Usar Bling. Não entrar no wizard sozinho.
    if st.session_state.get(MOBILE_AUTO_ENTRY_KEY):
        return
    st.session_state[MOBILE_AUTO_ENTRY_KEY] = True
    add_audit_event(
        'app_mobile_connected_bling_auto_entry_disabled_for_dual_home',
        area='HOME',
        status='OK',
        details={
            'reason': 'Home deve permanecer visível para o usuário escolher Mapear Planilha ou Bling.',
            'device_hint': _device_hint(),
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
    _install_device_autodetect_css()
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
    install_mapping_pagination_runtime()
    install_oauth_link_guard()
    _install_bling_api_verified_media_checkpoint('after_runtime_patches')
    bling_oauth.process_oauth_callback()
    _auto_enter_wizard_when_bling_connected_on_mobile()
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
