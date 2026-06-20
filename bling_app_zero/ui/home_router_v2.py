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
FLOW_WIZARD = 'wizard_cadastro_estoque'
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


def _start_bling_api_flow() -> None:
    try:
        legacy._start_wizard_context(legacy.CONTEXT_BLING_API, step=legacy.STEP_ORIGEM, api_send=True)
        legacy.safe_rerun('home_v2_use_connected_bling')
    except Exception:
        st.session_state[ACTIVE_FLOW_KEY] = FLOW_WIZARD
        st.session_state[HOME_ALLOW_FLOW_KEY] = True
        st.session_state['home_single_page_flow_active'] = True
        st.session_state['home_bling_connected_same_flow_api_send'] = True
        try:
            st.query_params['operation_v2'] = FLOW_WIZARD
            st.query_params.pop('step', None)
        except Exception:
            pass
        st.rerun()


def _price_multistore_requested() -> bool:
    return _query_param('operation_v2') == FLOW_PRICE_UPDATE or str(st.session_state.get(ACTIVE_FLOW_KEY) or '') == FLOW_PRICE_UPDATE


def _mapear_planilha_requested() -> bool:
    requested = _query_param('operation_v2').strip().lower()
    active = str(st.session_state.get(ACTIVE_FLOW_KEY) or '').strip().lower()
    return requested in MAPEAR_PLANILHA_ALIASES or active == FLOW_MAPEAR_PLANILHA


def _wizard_requested() -> bool:
    requested = _query_param('operation_v2').strip().lower()
    active = str(st.session_state.get(ACTIVE_FLOW_KEY) or '').strip().lower()
    return requested == FLOW_WIZARD or active == FLOW_WIZARD


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


def _render_home_style() -> None:
    st.markdown(
        '''
<style>
.mapeia-home-hero{border:1px solid rgba(15,23,42,.10);background:linear-gradient(135deg,#ffffff 0%,#f8fafc 100%);border-radius:22px;padding:1.05rem 1rem;margin:.35rem 0 1rem 0;box-shadow:0 14px 34px rgba(15,23,42,.06)}
.mapeia-home-eyebrow{font-size:.76rem;font-weight:900;color:#2563eb;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.35em}.mapeia-home-title{font-size:1.5rem;line-height:1.08;font-weight:950;color:#0f172a;margin:0}.mapeia-home-subtitle{font-size:.94rem;line-height:1.38;color:#475569;margin:.65rem 0 0 0}.mapeia-home-card{border:1px solid rgba(15,23,42,.09);background:#fff;border-radius:18px;padding:.95rem;margin:.72rem 0}.mapeia-home-card h3{font-size:1.05rem;margin:.05rem 0 .25rem;color:#0f172a}.mapeia-home-card p{font-size:.88rem;line-height:1.35;color:#64748b;margin:.2rem 0 .75rem}.mapeia-home-badge{display:inline-block;font-size:.72rem;font-weight:900;border-radius:999px;padding:.18rem .5rem;background:#eff6ff;color:#1d4ed8;margin-bottom:.4rem}.mapeia-home-muted{font-size:.82rem;color:#64748b;line-height:1.35}
</style>
''',
        unsafe_allow_html=True,
    )


def _render_mapear_planilha_primary_card() -> None:
    st.markdown(
        '''
<div class="mapeia-home-card">
  <span class="mapeia-home-badge">Principal · sem API</span>
  <h3>Mapear planilha sem API</h3>
  <p>Anexe a planilha fonte e o modelo final, use preço, categorização, mapeamento, recursos inteligentes, regras e IA, depois baixe o arquivo idêntico ao modelo.</p>
</div>
''',
        unsafe_allow_html=True,
    )
    if st.button('Mapear planilha sem API', use_container_width=True, key='home_start_mapear_planilha_sem_api_v2_primary'):
        start_mapear_planilha_flow()
        st.rerun()


def _render_bling_api_card() -> None:
    st.markdown(
        '''
<div class="mapeia-home-card">
  <span class="mapeia-home-badge">Bling/API</span>
  <h3>Conectar ou usar Bling</h3>
  <p>Use este caminho somente quando quiser enviar ao Bling pela API. O depósito/operação são definidos no fluxo, sem misturar com o mapeamento simples.</p>
</div>
''',
        unsafe_allow_html=True,
    )
    try:
        effective_status = legacy._effective_bling_status(try_sync=True)
    except Exception:
        effective_status = {'connected': False}
    connected = bool(effective_status.get('connected'))
    if connected:
        st.success('Bling conectado. Use este caminho apenas para envio/API.')
        if st.button('Usar Bling conectado / API', use_container_width=True, key='home_v2_use_connected_bling'):
            _start_bling_api_flow()
        return

    with st.expander('Conectar ao Bling para envio por API', expanded=False):
        try:
            auth_url = legacy.build_authorization_url({'return_to': 'home_v2_bling_entry', 'open_mode': 'android_safe'})
        except Exception as exc:
            auth_url = ''
            st.warning(f'Não consegui preparar o link do Bling agora: {exc}')
        try:
            legacy._render_bling_connection(auth_url)
        except Exception as exc:
            st.warning(f'Conexão Bling indisponível nesta sessão: {exc}')


def _render_price_multistore_home_entry() -> None:
    st.markdown(
        '''
<div class="mapeia-home-card">
  <span class="mapeia-home-badge">Preços</span>
  <h3>Atualizar preços multilojas</h3>
  <p>Caminho isolado para preço por loja/canal. Não passa por cadastro, estoque, categorias ou envio de produto.</p>
</div>
''',
        unsafe_allow_html=True,
    )
    if st.button('Atualizar preços multilojas', use_container_width=True, key='home_start_price_multistore_v2'):
        start_price_multistore_flow()
        st.rerun()


def _render_primary_home() -> None:
    try:
        legacy._reset_stale_flow_session_if_needed()
    except Exception:
        pass
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_HOME
    st.session_state[HOME_ALLOW_FLOW_KEY] = False
    st.session_state['home_single_page_flow_active'] = False

    _render_home_style()
    st.markdown(
        '''
<div class="mapeia-home-hero">
  <div class="mapeia-home-eyebrow">MapeiaAI</div>
  <h1 class="mapeia-home-title">Escolha o caminho antes de carregar os dados.</h1>
  <p class="mapeia-home-subtitle">A Home agora separa planilha sem API, Bling/API e preços multilojas para não misturar estado, depósito, cadastro, estoque ou download.</p>
</div>
''',
        unsafe_allow_html=True,
    )
    _render_mapear_planilha_primary_card()
    _render_bling_api_card()
    _render_price_multistore_home_entry()


def render_home() -> None:
    if _mapear_planilha_requested():
        _render_mapear_planilha_route()
        return
    if _price_multistore_requested():
        _render_price_multistore_route()
        return
    if _wizard_requested():
        legacy.render_home()
        return
    _render_primary_home()


__all__ = [
    'FLOW_MAPEAR_PLANILHA',
    'FLOW_PRICE_UPDATE',
    'render_home',
    'start_mapear_planilha_flow',
    'start_price_multistore_flow',
]
