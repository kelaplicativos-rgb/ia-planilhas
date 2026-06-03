from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from bling_app_zero.ui.flow_context import CONTEXT_BLING_API, CONTEXT_UNIVERSAL, activate_api_finish_mode, activate_csv_finish_mode, set_entry_context
from bling_app_zero.ui.home_wizard_rerun import set_step_without_rerun
from bling_app_zero.ui.scroll_position import request_scroll_top

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
FLOW_HOME = 'home'
FLOW_WIZARD = 'wizard_cadastro_estoque'
WIZARD_STEP_KEY = 'bling_wizard_step'
RESPONSIBLE_FILE = 'bling_app_zero/ui/bottom_nav.py'

STEP_MODELO = 'modelo'
STEP_ORIGEM = 'origem'
STEP_ENTRADA = 'entrada'
STEP_PRECIFICACAO = 'precificacao'
STEP_MAPEAMENTO = 'mapeamento'
STEP_REGRAS = 'regras'
STEP_DOWNLOAD = 'download'

FLOW_MENU_KEY = 'bottom_nav_fluxos_open'
LOG_MENU_KEY = 'bottom_nav_logs_open'

TECHNICAL_KEEP_PREFIXES = ('bling_token', 'bling_oauth', 'oauth')

SAFE_CLEAR_KEYS = (
    'site_capture_running',
    'site_capture_finished',
    'site_capture_error',
    'site_capture_started_at',
    'site_progress_log',
    'site_progress_last',
    'blingsmartscan_manual_continue_required',
    'blingsmartscan_ready_to_continue',
    'blingsmartscan_continue_target_step',
    'blingsmartscan_finished_operation',
    'blingsmartscan_finished_rows',
    'blingsmartscan_finished_columns',
    'blingsmartscan_budget_notice',
    'bling_api_batch_send_state_v2',
    'cadastro_entry_autoscroll_signature',
    'home_wizard_scroll_target_step',
    'wizard_bottom_nav_rendered_current_cycle',
)

SAFE_CLEAR_PREFIXES = (
    'site_deep_capture_',
    'site_capture_',
    'blingsmartscan_notice_',
    'blingsmartscan_report_',
    'bling_smart_sender_category_cache',
    'bling_smart_sender_product_cache',
)


def _clear_navigation_params() -> None:
    try:
        for key in ('operation_v2', 'step', 'flow', 'origem', 'operacao', 'operation'):
            st.query_params.pop(key, None)
    except Exception:
        pass


def _set_wizard_base(*, context: str, step: str, operation: str | None = None, origin: str | None = None, api_mode: bool = False) -> None:
    request_scroll_top()
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_WIZARD
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    st.session_state['home_single_page_flow_active'] = True
    set_entry_context(context)
    if api_mode:
        activate_api_finish_mode()
    else:
        activate_csv_finish_mode()
    if operation:
        st.session_state['direct_bling_operation_choice'] = operation
        st.session_state['home_slim_flow_operation'] = operation
        st.session_state['home_detected_operation'] = operation
        st.session_state['operacao_final'] = operation
        st.session_state['tipo_operacao_final'] = operation
        st.session_state['model_contract_type'] = operation
    if origin:
        st.session_state['home_slim_flow_origin'] = origin
        st.session_state['origem_final'] = origin
    set_step_without_rerun(step)
    try:
        st.query_params['operation_v2'] = FLOW_WIZARD
        st.query_params['step'] = step
        if operation:
            st.query_params['operation'] = operation
    except Exception:
        pass


def _go_home() -> None:
    request_scroll_top()
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_HOME
    st.session_state[HOME_ALLOW_FLOW_KEY] = False
    st.session_state['home_single_page_flow_active'] = False
    _clear_navigation_params()


def _go_api(operation: str, *, origin: str | None = None, step: str = STEP_ORIGEM) -> None:
    _set_wizard_base(context=CONTEXT_BLING_API, step=step, operation=operation, origin=origin, api_mode=True)


def _go_csv(operation: str, *, origin: str | None = None, step: str = STEP_MODELO) -> None:
    _set_wizard_base(context=CONTEXT_UNIVERSAL, step=step, operation=operation, origin=origin, api_mode=False)


def _go_universal(*, origin: str | None = None, step: str = STEP_MODELO) -> None:
    _set_wizard_base(context=CONTEXT_UNIVERSAL, step=step, operation='universal', origin=origin, api_mode=False)


def _refresh_screen() -> None:
    st.session_state['bottom_nav_last_refresh_at'] = time.time()
    st.rerun()


def _clear_streamlit_cache() -> None:
    try:
        st.cache_data.clear()
    except Exception:
        pass
    try:
        st.cache_resource.clear()
    except Exception:
        pass


def _safe_clear_stuck_state() -> None:
    for key in SAFE_CLEAR_KEYS:
        st.session_state.pop(key, None)
    for key in list(st.session_state.keys()):
        if key.startswith(SAFE_CLEAR_PREFIXES):
            st.session_state.pop(key, None)
    _clear_streamlit_cache()
    st.session_state['bottom_nav_last_safe_clear_at'] = time.time()


def _hard_reset_session() -> None:
    kept = {}
    for key, value in list(st.session_state.items()):
        if any(str(key).startswith(prefix) for prefix in TECHNICAL_KEEP_PREFIXES):
            kept[key] = value
    st.session_state.clear()
    for key, value in kept.items():
        st.session_state[key] = value
    _clear_streamlit_cache()
    _go_home()


def _dataframe_info(value: object) -> str:
    if isinstance(value, pd.DataFrame):
        return f'{len(value)}x{len(value.columns)}'
    return ''


def _render_fixed_css() -> None:
    st.markdown(
        '''
<style>
.bling-bottom-fixed-spacer{height:104px;}
div[data-testid="stVerticalBlock"]:has(> div .bling-bottom-nav-anchor){
    position:fixed;
    left:0;
    right:0;
    bottom:0;
    z-index:9999;
    padding:8px 10px calc(8px + env(safe-area-inset-bottom));
    background:rgba(255,255,255,.96);
    border-top:1px solid rgba(15,23,42,.10);
    box-shadow:0 -10px 30px rgba(15,23,42,.10);
    backdrop-filter:blur(12px);
}
div[data-testid="stVerticalBlock"]:has(> div .bling-bottom-nav-anchor) [data-testid="stHorizontalBlock"]{
    max-width:860px;
    margin:0 auto;
}
.bling-bottom-nav-anchor{
    color:#475569;
    font-size:.72rem;
    font-weight:700;
    text-align:center;
    margin-bottom:5px;
}
@media (max-width:520px){
    div[data-testid="stVerticalBlock"]:has(> div .bling-bottom-nav-anchor){padding-left:7px;padding-right:7px;}
    div[data-testid="stVerticalBlock"]:has(> div .bling-bottom-nav-anchor) button{font-size:.78rem;padding-left:.25rem;padding-right:.25rem;}
}
</style>
<div class="bling-bottom-fixed-spacer"></div>
''',
        unsafe_allow_html=True,
    )


def _context_is_api() -> bool:
    return str(st.session_state.get('bling_finish_mode') or '') == 'api_direct'


def _current_operation(default: str = 'cadastro') -> str:
    return str(st.session_state.get('direct_bling_operation_choice') or st.session_state.get('home_slim_flow_operation') or default)


def _render_fluxos_menu() -> None:
    if not bool(st.session_state.get(FLOW_MENU_KEY)):
        return
    with st.expander('⚡ Fluxos rápidos do sistema', expanded=True):
        st.caption('Atalhos diretos para os recursos principais detectados no BLINGSCAN.')
        st.markdown('##### API Bling')
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button('🛒 Cadastro API', use_container_width=True, key='bottom_flow_cadastro_api'):
                _go_api('cadastro', step=STEP_ORIGEM)
                st.rerun()
        with c2:
            if st.button('📦 Estoque API', use_container_width=True, key='bottom_flow_estoque_api'):
                _go_api('estoque', step=STEP_ORIGEM)
                st.rerun()
        with c3:
            if st.button('💲 Preços API', use_container_width=True, key='bottom_flow_precos_api'):
                _go_api('atualizacao_preco', step=STEP_ORIGEM)
                st.rerun()

        st.markdown('##### Origens rápidas')
        c4, c5 = st.columns(2)
        with c4:
            if st.button('🌐 Buscar em site', use_container_width=True, key='bottom_flow_site'):
                context = CONTEXT_BLING_API if _context_is_api() else CONTEXT_UNIVERSAL
                _set_wizard_base(context=context, step=STEP_ENTRADA, operation=_current_operation(), origin='site', api_mode=context == CONTEXT_BLING_API)
                st.rerun()
        with c5:
            if st.button('📎 Importar arquivo', use_container_width=True, key='bottom_flow_file'):
                context = CONTEXT_BLING_API if _context_is_api() else CONTEXT_UNIVERSAL
                _set_wizard_base(context=context, step=STEP_ENTRADA, operation=_current_operation(), origin='arquivo', api_mode=context == CONTEXT_BLING_API)
                st.rerun()

        st.markdown('##### CSV / planilha')
        c6, c7, c8 = st.columns(3)
        with c6:
            if st.button('📄 Cadastro CSV', use_container_width=True, key='bottom_flow_cadastro_csv'):
                _go_csv('cadastro')
                st.rerun()
        with c7:
            if st.button('📦 Estoque CSV', use_container_width=True, key='bottom_flow_estoque_csv'):
                _go_csv('estoque')
                st.rerun()
        with c8:
            if st.button('💲 Preços CSV', use_container_width=True, key='bottom_flow_precos_csv'):
                _go_csv('atualizacao_preco')
                st.rerun()

        st.markdown('##### Etapas internas')
        c9, c10, c11 = st.columns(3)
        with c9:
            if st.button('💰 Precificação', use_container_width=True, key='bottom_flow_pricing'):
                _go_universal(step=STEP_PRECIFICACAO)
                st.rerun()
        with c10:
            if st.button('🗺️ Mapeamento', use_container_width=True, key='bottom_flow_mapping'):
                _go_universal(step=STEP_MAPEAMENTO)
                st.rerun()
        with c11:
            if st.button('✅ Regras', use_container_width=True, key='bottom_flow_rules'):
                _go_universal(step=STEP_REGRAS)
                st.rerun()

        c12, c13, c14 = st.columns(3)
        with c12:
            if st.button('⬇️ Download/Enviar', use_container_width=True, key='bottom_flow_download'):
                context = CONTEXT_BLING_API if _context_is_api() else CONTEXT_UNIVERSAL
                _set_wizard_base(context=context, step=STEP_DOWNLOAD, operation=_current_operation(), api_mode=context == CONTEXT_BLING_API)
                st.rerun()
        with c13:
            if st.button('📁 Modelos', use_container_width=True, key='bottom_flow_models'):
                _go_universal(step=STEP_MODELO)
                st.rerun()
        with c14:
            if st.button('🏠 Início', use_container_width=True, key='bottom_flow_home'):
                _go_home()
                st.rerun()


def _render_logs_menu() -> None:
    if not bool(st.session_state.get(LOG_MENU_KEY)):
        return
    with st.expander('🧪 Diagnóstico rápido', expanded=True):
        active_flow = str(st.session_state.get(ACTIVE_FLOW_KEY) or '').strip() or 'home'
        step = str(st.session_state.get(WIZARD_STEP_KEY) or '').strip() or '-'
        operation = str(st.session_state.get('direct_bling_operation_choice') or st.session_state.get('home_slim_flow_operation') or st.session_state.get('operacao_final') or '-').strip()
        origin = str(st.session_state.get('home_slim_flow_origin') or st.session_state.get('origem_final') or '-').strip()
        st.caption(f'Fluxo: {active_flow} · Etapa: {step} · Operação: {operation} · Origem: {origin}')
        data_keys = [
            'df_site_bruto_cadastro',
            'df_site_bruto_estoque',
            'df_origem_site_como_planilha_cadastro',
            'df_origem_site_como_planilha_estoque',
            'cadastro_wizard_df_origem',
            'cadastro_wizard_df_para_mapear',
            'df_final_download',
        ]
        rows = []
        for key in data_keys:
            info = _dataframe_info(st.session_state.get(key))
            if info:
                rows.append({'chave': key, 'tamanho': info})
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.caption('Nenhum DataFrame principal carregado nesta sessão.')
        if st.button('🧹 Limpeza total da sessão', use_container_width=True, key='bottom_hard_reset_confirm'):
            _hard_reset_session()
            st.rerun()


def render_bottom_nav() -> None:
    _render_fixed_css()
    _render_fluxos_menu()
    _render_logs_menu()

    with st.container():
        st.markdown('<div class="bling-bottom-nav-anchor">Atalhos rápidos · refresh · limpeza · fluxos</div>', unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button('🔄 Refresh', key='bottom_nav_refresh', use_container_width=True):
                _refresh_screen()
        with col2:
            if st.button('🧹 Limpar', key='bottom_nav_safe_clear', use_container_width=True):
                _safe_clear_stuck_state()
                st.rerun()
        with col3:
            if st.button('⚡ Fluxos', key='bottom_nav_fluxos', use_container_width=True):
                st.session_state[FLOW_MENU_KEY] = not bool(st.session_state.get(FLOW_MENU_KEY))
                st.session_state[LOG_MENU_KEY] = False
                st.rerun()
        with col4:
            if st.button('🧪 Logs', key='bottom_nav_logs', use_container_width=True):
                st.session_state[LOG_MENU_KEY] = not bool(st.session_state.get(LOG_MENU_KEY))
                st.session_state[FLOW_MENU_KEY] = False
                st.rerun()


__all__ = ['render_bottom_nav']
