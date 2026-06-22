from __future__ import annotations

import pandas as pd
import streamlit as st

import bling_app_zero.ui.home_router as legacy
from bling_app_zero.ui.flow_context import CONTEXT_BLING_API, CONTEXT_UNIVERSAL, activate_csv_finish_mode, set_entry_context
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
KNOWN_FLOWS = {FLOW_HOME, FLOW_WIZARD, FLOW_PRICE_UPDATE, FLOW_MAPEAR_PLANILHA}

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
    'api_flow_active',
)

BLING_ONLY_STATE_KEYS = (
    'cadastro_wizard_df_modelo',
    'cadastro_wizard_df_modelo_estoque',
    'df_modelo_cadastro',
    'df_modelo_estoque',
    'modelo_cadastro_df',
    'modelo_estoque_df',
    'home_modelo_cadastro_df',
    'home_modelo_estoque_df',
    'estoque_wizard_df_modelo',
    'df_final_bling_api',
    'mapping_bling_api',
    'mapping_confidence_bling_api',
    'bling_api_stock_deposit_name',
    'bling_api_stock_deposit_id',
)

UNIVERSAL_RUNTIME_KEYS_TO_LEAVE_BLING = (
    'mapear_planilha_sem_api_active',
    'mapeiaai_universal_source_df',
    'mapeiaai_universal_mapping',
    'mapeiaai_universal_output_df',
    'mapeiaai_universal_signature',
    'mapeiaai_universal_mapping_engine',
    'mapeiaai_universal_source_kind',
    'df_origem_unificada',
    'df_origem_site',
    'df_origem_arquivo',
)

UNIVERSAL_MODEL_KEYS = (
    'mapeiaai_universal_model_df',
    'home_modelo_universal_df',
    'df_modelo_universal',
    'modelo_universal_df',
)

UNIVERSAL_OPERATION_KEYS = (
    'mapeiaai_universal_model_df',
    'mapeiaai_universal_source_df',
    'mapeiaai_universal_mapping',
    'mapeiaai_universal_output_df',
    'mapeiaai_universal_signature',
    'mapeiaai_universal_mapping_engine',
    'mapeiaai_universal_source_kind',
    'df_origem_unificada',
    'df_origem_site',
    'df_origem_arquivo',
    'neutral_mapping_state_v1',
    'neutral_mapping_report_v1',
    'neutral_final_output_state_v1',
    'neutral_final_output_report_v1',
    'mapeiaai_universal_model_upload',
    'mapeiaai_universal_source_upload',
    'mapeiaai_universal_source_mode',
    'mapeiaai_universal_site_urls',
    'mapeiaai_universal_site_all_products',
    'mapeiaai_universal_toggle_price',
    'mapeiaai_universal_toggle_category',
    'mapeiaai_universal_toggle_mapping_auto',
    'mapeiaai_universal_toggle_mapping_ai',
    'mapeiaai_universal_toggle_rules',
)

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
    for key in BLING_ONLY_STATE_KEYS:
        st.session_state.pop(key, None)
    set_entry_context(CONTEXT_UNIVERSAL)
    activate_csv_finish_mode()
    st.session_state['mapeiaai_flow_kind'] = 'universal_model_mapping'
    st.session_state['flow_kind'] = 'universal_model_mapping'
    st.session_state['api_flow_active'] = False
    st.session_state['active_feature_mode'] = 'csv'
    st.session_state['active_feature_operation'] = 'universal'
    st.session_state['active_feature_contract_key'] = 'universal_mapping_csv'
    st.session_state['flow_spine_contract_key'] = 'universal_mapping_csv'
    st.session_state['flow_spine_operation'] = 'universal'
    st.session_state['flow_spine_final_destination'] = 'download'
    st.session_state['flow_spine_final_title'] = 'Download'
    st.session_state['flow_spine_primary_action_label'] = 'Download Modelo Mapeado'
    legacy.add_audit_event(
        'home_router_v2_no_api_context_isolated',
        area='HOME',
        status='OK',
        details={'responsible_file': RESPONSIBLE_FILE, 'flow_kind': 'universal_model_mapping', 'api': False},
    )


def _clear_universal_operation_state(*, keep_model: bool = False) -> None:
    preserved_model = st.session_state.get('mapeiaai_universal_model_df') if keep_model else None
    for key in UNIVERSAL_OPERATION_KEYS:
        st.session_state.pop(key, None)
    for key in list(st.session_state.keys()):
        text_key = str(key)
        if text_key.startswith('mapeiaai_universal_map_') or text_key.startswith('mapeiaai_shared_map_'):
            st.session_state.pop(key, None)
    if not keep_model:
        for key in UNIVERSAL_MODEL_KEYS:
            st.session_state.pop(key, None)
    elif isinstance(preserved_model, pd.DataFrame):
        clean = preserved_model.copy().fillna('')
        st.session_state['mapeiaai_universal_model_df'] = clean
        for key in ('home_modelo_universal_df', 'df_modelo_universal', 'modelo_universal_df'):
            st.session_state[key] = clean
    legacy.add_audit_event(
        'home_router_v2_universal_operation_state_cleared',
        area='HOME',
        status='OK',
        details={'responsible_file': RESPONSIBLE_FILE, 'keep_model': bool(keep_model)},
    )


def _reset_stale_home_flow_if_needed() -> None:
    requested = _query_param('operation_v2').strip().lower()
    active = str(st.session_state.get(ACTIVE_FLOW_KEY) or FLOW_HOME).strip().lower()
    if requested:
        return
    stale_wizard = active == FLOW_WIZARD and not (
        bool(st.session_state.get(HOME_ALLOW_FLOW_KEY))
        and bool(st.session_state.get('home_single_page_flow_active'))
    )
    unknown_flow = active not in KNOWN_FLOWS
    if not stale_wizard and not unknown_flow:
        return
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_HOME
    st.session_state[HOME_ALLOW_FLOW_KEY] = False
    st.session_state['home_single_page_flow_active'] = False
    st.session_state.pop('mapeiaai_home_entry_path', None)
    legacy.add_audit_event(
        'home_router_v2_stale_flow_reset_to_dual_home',
        area='HOME',
        status='OK',
        details={
            'previous_active_flow': active,
            'reason': 'Sessao antiga ou fluxo legado sem rota valida; Home dual deve ser o ponto de decisao.',
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


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
    st.session_state['mapeiaai_home_entry_path'] = 'mapear_modelo_sem_api'
    st.session_state['mapeiaai_flow_kind'] = 'universal_model_mapping'
    st.session_state['flow_kind'] = 'universal_model_mapping'
    st.session_state['api_flow_active'] = False
    st.session_state['bling_wizard_step'] = 'modelo'
    st.session_state['home_wizard_step'] = 'modelo'
    st.session_state['home_slim_flow_operation'] = 'universal'
    st.session_state['operacao_final'] = 'universal'
    st.session_state['tipo_operacao_final'] = 'universal'
    st.session_state['home_detected_operation'] = 'universal'
    try:
        st.query_params['operation_v2'] = FLOW_MAPEAR_PLANILHA
        for key in ('step', 'flow', 'origem', 'operacao', 'operation'):
            st.query_params.pop(key, None)
    except Exception:
        pass


def start_bling_api_flow() -> None:
    st.session_state['mapeiaai_home_entry_path'] = 'bling_api'
    st.session_state['mapeiaai_flow_kind'] = 'bling_api'
    st.session_state['flow_kind'] = 'bling_api'
    st.session_state['api_flow_active'] = True
    st.session_state['home_bling_connected_same_flow_api_send'] = True
    st.session_state['bling_connected_api_flow_active'] = True
    st.session_state.pop('mapear_planilha_sem_api_active', None)
    for key in UNIVERSAL_RUNTIME_KEYS_TO_LEAVE_BLING:
        st.session_state.pop(key, None)
    try:
        legacy._start_wizard_context(CONTEXT_BLING_API, step='origem', api_send=True)
    except Exception:
        st.session_state[ACTIVE_FLOW_KEY] = FLOW_WIZARD
        st.session_state[HOME_ALLOW_FLOW_KEY] = True
        st.session_state['home_single_page_flow_active'] = True
        st.session_state['bling_wizard_step'] = 'origem'
        st.session_state['home_wizard_step'] = 'origem'
    try:
        st.query_params['operation_v2'] = FLOW_WIZARD
        st.query_params['step'] = 'origem'
    except Exception:
        pass
    legacy.add_audit_event(
        'home_router_v2_bling_api_context_isolated',
        area='HOME',
        status='OK',
        details={'responsible_file': RESPONSIBLE_FILE, 'flow_kind': 'bling_api', 'api': True, 'first_step': 'origem'},
    )


def _price_multistore_requested() -> bool:
    return _query_param('operation_v2') == FLOW_PRICE_UPDATE or str(st.session_state.get(ACTIVE_FLOW_KEY) or '') == FLOW_PRICE_UPDATE


def _mapear_planilha_requested() -> bool:
    requested = _query_param('operation_v2').strip().lower()
    active = str(st.session_state.get(ACTIVE_FLOW_KEY) or '').strip().lower()
    return requested in MAPEAR_PLANILHA_ALIASES or active == FLOW_MAPEAR_PLANILHA


def _wizard_requested() -> bool:
    requested = _query_param('operation_v2').strip().lower()
    if requested == FLOW_WIZARD:
        return True
    active = str(st.session_state.get(ACTIVE_FLOW_KEY) or '').strip().lower()
    if active != FLOW_WIZARD:
        return False
    return bool(st.session_state.get(HOME_ALLOW_FLOW_KEY)) and bool(st.session_state.get('home_single_page_flow_active'))


def _go_home_from_independent_flow() -> None:
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_HOME
    st.session_state[HOME_ALLOW_FLOW_KEY] = False
    st.session_state['home_single_page_flow_active'] = False
    st.session_state.pop('price_multistore_independent_route_active', None)
    st.session_state.pop('mapear_planilha_sem_api_active', None)
    st.session_state.pop('mapeiaai_home_entry_path', None)
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
        st.caption('Fluxo independente sem API: anexe o modelo final, escolha origem dos dados, revise o mapeamento e baixe a planilha idêntica.')

    has_model = isinstance(st.session_state.get('mapeiaai_universal_model_df'), pd.DataFrame)
    has_source = isinstance(st.session_state.get('mapeiaai_universal_source_df'), pd.DataFrame)
    if has_model or has_source:
        st.info('Operação anterior detectada. Para criar uma nova planilha, limpe o estado antigo antes de anexar o novo modelo.')
        col_new, col_source = st.columns(2)
        with col_new:
            if st.button('🧹 Nova planilha / anexar novo modelo', use_container_width=True, key='mapear_planilha_nova_planilha_v2'):
                _clear_universal_operation_state(keep_model=False)
                start_mapear_planilha_flow()
                st.rerun()
        with col_source:
            if has_model and st.button('↻ Trocar somente a origem', use_container_width=True, key='mapear_planilha_trocar_origem_v2'):
                _clear_universal_operation_state(keep_model=True)
                start_mapear_planilha_flow()
                st.rerun()
    render_universal_flow()


def _active_flow_is_home() -> bool:
    active_flow = str(st.session_state.get(ACTIVE_FLOW_KEY) or FLOW_HOME).strip()
    return active_flow in {'', FLOW_HOME}


def _render_bling_connection_panel() -> None:
    try:
        auth_url = legacy.build_authorization_url({'return_to': 'mapeiaai_home_bling', 'open_mode': 'android_safe'})
    except Exception as exc:
        auth_url = ''
        st.warning(f'Não consegui preparar o link do Bling agora: {exc}')
    legacy._render_bling_connection(auth_url)


def _render_mapeiaai_home_entry() -> None:
    if not _active_flow_is_home():
        return
    try:
        legacy._reset_stale_flow_session_if_needed()
    except Exception:
        pass
    effective_status = legacy._effective_bling_status(try_sync=True)
    connected = bool(effective_status.get('connected'))
    st.markdown(
        '''
<style>
.mapeiaai-home-hero{border:1px solid rgba(15,23,42,.10);background:linear-gradient(135deg,#ffffff 0%,#f8fafc 100%);border-radius:22px;padding:1.05rem 1rem;margin:.35rem 0 1rem 0;box-shadow:0 14px 34px rgba(15,23,42,.06)}
.mapeiaai-home-eyebrow{font-size:.78rem;font-weight:800;color:#2563eb;text-transform:uppercase;letter-spacing:.08em;margin-bottom:.35em}.mapeiaai-home-title{font-size:1.55rem;line-height:1.08;font-weight:950;color:#0f172a;margin:0}.mapeiaai-home-subtitle{font-size:.95rem;line-height:1.38;color:#475569;margin:.65rem 0 0 0}.mapeiaai-home-card{border:1px solid rgba(15,23,42,.09);background:#fff;border-radius:18px;padding:.95rem;margin:.65rem 0}.mapeiaai-home-card strong{color:#0f172a}.mapeiaai-home-muted{font-size:.84rem;color:#64748b;line-height:1.35}
</style>
<div class="mapeiaai-home-hero">
  <div class="mapeiaai-home-eyebrow">MapeiaAI</div>
  <h1 class="mapeiaai-home-title">Escolha o caminho da operação</h1>
  <p class="mapeiaai-home-subtitle">O núcleo universal mapeia qualquer modelo de planilha. O núcleo Bling conecta a API e envia cadastro, atualização de produtos ou estoque.</p>
</div>
''',
        unsafe_allow_html=True,
    )
    col_mapear, col_bling = st.columns(2)
    with col_mapear:
        st.markdown('<div class="mapeiaai-home-card"><strong>Anexar Modelo / Mapear</strong><br><span class="mapeiaai-home-muted">Sem API. Primeiro anexe o modelo final, depois busque origem por site ou arquivo, use toggles opcionais, veja o preview e baixe a planilha idêntica.</span></div>', unsafe_allow_html=True)
        if st.button('📄 Anexar Modelo / Mapear Planilha', use_container_width=True, key='home_core_mapear_modelo_v2'):
            _clear_universal_operation_state(keep_model=False)
            start_mapear_planilha_flow()
            st.rerun()
    with col_bling:
        status = 'Bling conectado' if connected else 'Conectar ao Bling'
        st.markdown(f'<div class="mapeiaai-home-card"><strong>{status}</strong><br><span class="mapeiaai-home-muted">Com API. Conecta ao Bling, cai em origem de dados, escolhe Atualizar Estoque, Cadastro ou Atualizar Produtos, revisa e envia.</span></div>', unsafe_allow_html=True)
        button_label = '🔗 Usar Bling conectado' if connected else '🔗 Conectar ao Bling'
        if st.button(button_label, use_container_width=True, key='home_core_connect_bling_v2'):
            if connected:
                start_bling_api_flow()
                st.rerun()
            else:
                st.session_state['home_show_bling_connection_panel_v2'] = True
                st.rerun()
    if connected:
        st.success('Bling conectado. Ao tocar em “Usar Bling conectado”, o fluxo começa em Origem de dados e o envio aparece somente no final.')
    elif bool(st.session_state.get('home_show_bling_connection_panel_v2')):
        st.markdown('---')
        st.markdown('### Conectar ao Bling')
        _render_bling_connection_panel()
    legacy.add_audit_event('home_router_v2_render_mapeiaai_dual_core_home', area='HOME', status='OK', details={'responsible_file': RESPONSIBLE_FILE, 'home_paths': ['mapear_modelo_sem_api', 'bling_api'], 'connected': connected, 'bling_first_step_after_connection': 'origem', 'universal_first_step': 'modelo'})


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
    _reset_stale_home_flow_if_needed()
    if _mapear_planilha_requested():
        _render_mapear_planilha_route()
        return
    if _price_multistore_requested():
        _render_price_multistore_route()
        return
    if _wizard_requested():
        legacy.render_home()
        return
    _render_mapeiaai_home_entry()
    _render_price_multistore_home_entry()


__all__ = [
    'FLOW_MAPEAR_PLANILHA',
    'FLOW_PRICE_UPDATE',
    'render_home',
    'start_bling_api_flow',
    'start_mapear_planilha_flow',
    'start_price_multistore_flow',
]
