from __future__ import annotations

import time
from urllib.parse import urlencode

import pandas as pd
import streamlit as st

from bling_app_zero.core.app_actions import (
    ACTION_CLEAR,
    ACTION_DIAGNOSTIC,
    ACTION_PARAM,
    ACTION_REFRESH,
    ACTION_SHORTCUTS,
    BOTTOM_BAR_ACTIONS,
    SAFE_CLEAR_KEYS,
    SAFE_CLEAR_PREFIXES,
    TECHNICAL_KEEP_PREFIXES,
    is_known_action,
)
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


def _query_value(name: str) -> str:
    try:
        value = st.query_params.get(name, '')
        if isinstance(value, list):
            return str(value[0] if value else '').strip()
        return str(value or '').strip()
    except Exception:
        return ''


def _remove_action_param() -> None:
    try:
        st.query_params.pop(ACTION_PARAM, None)
    except Exception:
        pass


def _href_for_action(action: str) -> str:
    params: dict[str, object] = {}
    try:
        for key, value in dict(st.query_params).items():
            if key == ACTION_PARAM:
                continue
            params[str(key)] = value
    except Exception:
        params = {}
    params[ACTION_PARAM] = action
    return '?' + urlencode(params, doseq=True)


def _handle_bottom_action() -> None:
    action = _query_value(ACTION_PARAM)
    if not action:
        return
    _remove_action_param()
    if not is_known_action(action):
        return
    if action == ACTION_REFRESH:
        _refresh_screen()
    if action == ACTION_CLEAR:
        _safe_clear_stuck_state()
        st.rerun()
    if action == ACTION_SHORTCUTS:
        st.session_state[FLOW_MENU_KEY] = not bool(st.session_state.get(FLOW_MENU_KEY))
        st.session_state[LOG_MENU_KEY] = False
        return
    if action == ACTION_DIAGNOSTIC:
        st.session_state[LOG_MENU_KEY] = not bool(st.session_state.get(LOG_MENU_KEY))
        st.session_state[FLOW_MENU_KEY] = False
        return


def _render_fixed_css() -> None:
    st.markdown(
        '''
<style>
.bling-bottom-fixed-spacer{height:110px;}
.bling-bottom-fixed{
    position:fixed;
    left:0;
    right:0;
    bottom:0;
    z-index:2147483000;
    padding:8px 10px calc(8px + env(safe-area-inset-bottom));
    background:rgba(255,255,255,.97);
    border-top:1px solid rgba(15,23,42,.12);
    box-shadow:0 -10px 30px rgba(15,23,42,.12);
    backdrop-filter:blur(12px);
    -webkit-backdrop-filter:blur(12px);
}
.bling-bottom-fixed-label{
    max-width:860px;
    margin:0 auto 5px auto;
    color:#475569;
    font-size:.72rem;
    font-weight:700;
    text-align:center;
    line-height:1.1;
}
.bling-bottom-fixed-grid{
    max-width:860px;
    margin:0 auto;
    display:grid;
    grid-template-columns:repeat(4,minmax(0,1fr));
    gap:6px;
}
.bling-bottom-fixed-grid a{
    display:flex;
    align-items:center;
    justify-content:center;
    min-height:38px;
    padding:7px 5px;
    border-radius:12px;
    border:1px solid rgba(15,23,42,.16);
    background:#fff;
    color:#0f172a!important;
    text-decoration:none!important;
    font-weight:800;
    font-size:.84rem;
    box-shadow:0 1px 4px rgba(15,23,42,.08);
    white-space:nowrap;
}
.bling-bottom-fixed-grid a:active{transform:translateY(1px);}
@media (max-width:520px){
    .bling-bottom-fixed{padding-left:7px;padding-right:7px;}
    .bling-bottom-fixed-grid{gap:4px;}
    .bling-bottom-fixed-grid a{font-size:.74rem;min-height:36px;padding-left:3px;padding-right:3px;border-radius:10px;}
    .bling-bottom-fixed-label{font-size:.68rem;}
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
    with st.expander('⚡ Atalhos rápidos', expanded=True):
        st.caption('Acesse rapidamente as principais ações do sistema.')
        st.markdown('##### Enviar direto ao Bling')
        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button('🛒 Cadastrar produtos', use_container_width=True, key='bottom_flow_cadastro_api'):
                _go_api('cadastro', step=STEP_ORIGEM)
                st.rerun()
        with c2:
            if st.button('📦 Atualizar estoque', use_container_width=True, key='bottom_flow_estoque_api'):
                _go_api('estoque', step=STEP_ORIGEM)
                st.rerun()
        with c3:
            if st.button('💲 Atualizar preços', use_container_width=True, key='bottom_flow_precos_api'):
                _go_api('atualizacao_preco', step=STEP_ORIGEM)
                st.rerun()

        st.markdown('##### Entrada de dados')
        c4, c5 = st.columns(2)
        with c4:
            if st.button('🌐 Buscar no site', use_container_width=True, key='bottom_flow_site'):
                context = CONTEXT_BLING_API if _context_is_api() else CONTEXT_UNIVERSAL
                _set_wizard_base(context=context, step=STEP_ENTRADA, operation=_current_operation(), origin='site', api_mode=context == CONTEXT_BLING_API)
                st.rerun()
        with c5:
            if st.button('📎 Importar planilha', use_container_width=True, key='bottom_flow_file'):
                context = CONTEXT_BLING_API if _context_is_api() else CONTEXT_UNIVERSAL
                _set_wizard_base(context=context, step=STEP_ENTRADA, operation=_current_operation(), origin='arquivo', api_mode=context == CONTEXT_BLING_API)
                st.rerun()

        st.markdown('##### Gerar arquivo')
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

        st.markdown('##### Ferramentas')
        c9, c10, c11 = st.columns(3)
        with c9:
            if st.button('💰 Precificar', use_container_width=True, key='bottom_flow_pricing'):
                _go_universal(step=STEP_PRECIFICACAO)
                st.rerun()
        with c10:
            if st.button('🗺️ Mapear campos', use_container_width=True, key='bottom_flow_mapping'):
                _go_universal(step=STEP_MAPEAMENTO)
                st.rerun()
        with c11:
            if st.button('✅ Revisar regras', use_container_width=True, key='bottom_flow_rules'):
                _go_universal(step=STEP_REGRAS)
                st.rerun()

        c12, c13, c14 = st.columns(3)
        with c12:
            if st.button('⬇️ Enviar/Baixar', use_container_width=True, key='bottom_flow_download'):
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
        st.caption(f'Caminho atual: {active_flow} · Etapa: {step} · Operação: {operation} · Origem: {origin}')
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
                rows.append({'dado': key, 'tamanho': info})
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.caption('Nenhum dado principal carregado nesta sessão.')
        if st.button('🧹 Limpeza total da sessão', use_container_width=True, key='bottom_hard_reset_confirm'):
            _hard_reset_session()
            st.rerun()


def _render_html_bottom_bar() -> None:
    links = '\n'.join(
        f'    <a href="{_href_for_action(action.key)}">{action.title}</a>'
        for action in BOTTOM_BAR_ACTIONS
    )
    st.markdown(
        f'''
<div class="bling-bottom-fixed">
  <div class="bling-bottom-fixed-label">Ações rápidas · atualizar · limpar · diagnosticar</div>
  <div class="bling-bottom-fixed-grid">
{links}
  </div>
</div>
''',
        unsafe_allow_html=True,
    )


def render_bottom_nav() -> None:
    _handle_bottom_action()
    _render_fixed_css()
    _render_fluxos_menu()
    _render_logs_menu()
    _render_html_bottom_bar()


__all__ = ['render_bottom_nav']
