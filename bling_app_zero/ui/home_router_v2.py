from __future__ import annotations

import streamlit as st

import bling_app_zero.ui.home_router as legacy
from bling_app_zero.ui.flow_context import CONTEXT_UNIVERSAL, activate_csv_finish_mode, set_entry_context
from bling_app_zero.ui.home_wizard_v2 import STEP_CATEGORIZACAO, render_home_wizard
from bling_app_zero.ui.universal_flow import render_universal_flow
from bling_app_zero.v2.price_multistore.ui_plus import render_price_multistore_v2

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_router_v2.py'
ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
FLOW_HOME = 'home'
FLOW_PRICE_UPDATE = 'price_multistore_v2'
FLOW_MAPEAR_PLANILHA = 'mapear_planilha'

MAPEAR_PLANILHA_ALIASES = {
    FLOW_MAPEAR_PLANILHA,
    'mapear-planilha',
    'mapear_planilha_sem_api',
    'planilha_sem_api',
    'universal_csv',
    'universal_mapping_csv',
}

NO_API_SESSION_KEYS = (
    'home_bling_connected_same_flow_api_send',
    'bling_connected_api_flow_active',
    'direct_bling_api_contract_active',
    'direct_bling_operation_applied',
    'direct_bling_api_contract_df',
    'bling_api_operation',
    'api_operation',
    'home_bling_api_operation_choice',
    'bling_connected_api_operation',
    'flow_spine_sender_operation',
    'flow_spine_operation_resolved_for_api',
    'flow_spine_api_batch_operation',
    'source_first_selected_operation',
    'source_first_operation_user_confirmed',
    'source_first_operation_pending_choice',
    'bling_api_required_selector',
    'bling_api_final_action',
    'bling_api_manual_mapping_required',
    'bling_api_must_run_ai_check',
)

# O router legado importa render_home_wizard uma vez. Este patch troca a rota por uma
# versão que contém a etapa independente de Conferência e Correção de Categorias.
legacy.render_home_wizard = render_home_wizard
try:
    legacy.VALID_SINGLE_PAGE_STEPS.add(STEP_CATEGORIZACAO)
except Exception:
    pass


def _query_param(name: str) -> str:
    try:
        value = st.query_params.get(name)
    except Exception:
        return ''
    if isinstance(value, list):
        return str(value[0] if value else '').strip()
    return str(value or '').strip()


def _clear_no_api_session_flags() -> None:
    for key in NO_API_SESSION_KEYS:
        st.session_state.pop(key, None)
    set_entry_context(CONTEXT_UNIVERSAL)
    activate_csv_finish_mode()
    st.session_state['active_feature_mode'] = 'csv'
    st.session_state['active_feature_operation'] = 'universal'
    st.session_state['active_feature_contract_key'] = 'universal_mapping_csv'
    st.session_state['flow_spine_contract_key'] = 'universal_mapping_csv'
    st.session_state['flow_spine_operation'] = 'universal'
    st.session_state['flow_spine_final_destination'] = 'download'
    st.session_state['flow_spine_final_title'] = 'Download'
    st.session_state['flow_spine_primary_action_label'] = 'Download Modelo Mapeado'


def start_price_multistore_flow() -> None:
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_PRICE_UPDATE
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    st.session_state['home_single_page_flow_active'] = False
    try:
        st.query_params['operation_v2'] = FLOW_PRICE_UPDATE
        st.query_params.pop('step', None)
    except Exception:
        pass


def start_mapear_planilha_flow() -> None:
    _clear_no_api_session_flags()
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_MAPEAR_PLANILHA
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    st.session_state['home_single_page_flow_active'] = False
    st.session_state['mapear_planilha_sem_api_active'] = True
    try:
        st.query_params['operation_v2'] = FLOW_MAPEAR_PLANILHA
        for key in ('step', 'flow', 'origem', 'operacao', 'operation'):
            st.query_params.pop(key, None)
    except Exception:
        pass


def _price_multistore_requested() -> bool:
    return _query_param('operation_v2') == FLOW_PRICE_UPDATE or str(st.session_state.get(ACTIVE_FLOW_KEY) or '') == FLOW_PRICE_UPDATE


def _mapear_planilha_requested() -> bool:
    requested = _query_param('operation_v2').strip().lower()
    active = str(st.session_state.get(ACTIVE_FLOW_KEY) or '').strip().lower()
    return requested in MAPEAR_PLANILHA_ALIASES or active == FLOW_MAPEAR_PLANILHA


def _go_home_from_independent_flow() -> None:
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_HOME
    st.session_state[HOME_ALLOW_FLOW_KEY] = False
    st.session_state['home_single_page_flow_active'] = False
    st.session_state.pop('price_multistore_independent_route_active', None)
    st.session_state.pop('mapear_planilha_sem_api_active', None)
    try:
        st.query_params.pop('operation_v2', None)
        st.query_params.pop('step', None)
    except Exception:
        pass
    st.rerun()


def _render_price_multistore_route() -> None:
    start_price_multistore_flow()
    st.session_state['price_multistore_independent_route_active'] = True
    col_back, col_title = st.columns([1, 3])
    with col_back:
        if st.button('Voltar ao início', use_container_width=True, key='price_multistore_back_home_v2'):
            _go_home_from_independent_flow()
    with col_title:
        st.caption('Fluxo independente: não passa por cadastro, estoque, categorias ou Regras e IA.')
    render_price_multistore_v2()


def _render_mapear_planilha_route() -> None:
    start_mapear_planilha_flow()
    col_back, col_title = st.columns([1, 3])
    with col_back:
        if st.button('Voltar ao início', use_container_width=True, key='mapear_planilha_back_home_v2'):
            _go_home_from_independent_flow()
    with col_title:
        st.caption('Fluxo independente sem API: anexe a planilha fonte, anexe o modelo final, revise o mapeamento e baixe o arquivo.')
    render_universal_flow()


def _active_flow_is_home() -> bool:
    active_flow = str(st.session_state.get(ACTIVE_FLOW_KEY) or FLOW_HOME).strip()
    return active_flow in {'', FLOW_HOME}


def _render_mapear_planilha_home_entry() -> None:
    if not _active_flow_is_home():
        return
    st.markdown('---')
    st.markdown('### Mapear planilha sem API')
    st.caption('Use este caminho para qualquer marketplace, fornecedor ou modelo próprio. Não conecta, não envia e não depende do Bling.')
    if st.button('Mapear planilha', use_container_width=True, key='home_start_mapear_planilha_sem_api_v2'):
        start_mapear_planilha_flow()
        st.rerun()


def _render_price_multistore_home_entry() -> None:
    if not _active_flow_is_home():
        return
    st.markdown('---')
    st.markdown('### Fluxo independente')
    st.caption('Use este caminho somente para atualizar preços por loja/canal. Ele não passa pelo wizard de cadastro/estoque.')
    if st.button('Atualizar preços multilojas', use_container_width=True, key='home_start_price_multistore_v2'):
        start_price_multistore_flow()
        st.rerun()


def render_home() -> None:
    if _mapear_planilha_requested():
        _render_mapear_planilha_route()
        return
    if _price_multistore_requested():
        _render_price_multistore_route()
        return
    legacy.render_home()
    _render_mapear_planilha_home_entry()
    _render_price_multistore_home_entry()


__all__ = [
    'FLOW_MAPEAR_PLANILHA',
    'FLOW_PRICE_UPDATE',
    'render_home',
    'start_mapear_planilha_flow',
    'start_price_multistore_flow',
]
