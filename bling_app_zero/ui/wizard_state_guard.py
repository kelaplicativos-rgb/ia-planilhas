from __future__ import annotations

import streamlit as st

from bling_app_zero.universal.model_contract_detector import MODEL_CONTRACT_TYPE_KEY, normalize_contract_operation

WIZARD_STEP_KEY = 'bling_wizard_step'
FLOW_OPERATION_KEY = 'home_slim_flow_operation'
FLOW_ORIGIN_KEY = 'home_slim_flow_origin'
STATE_GUARD_VERSION_KEY = 'bling_wizard_state_guard_version'
STATE_GUARD_LAST_OPERATION_KEY = 'bling_wizard_state_guard_last_operation'
STATE_GUARD_VERSION = '2026-05-27-blingreset-context-guard-1'
HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'

VALID_STEPS = {
    'modelo',
    'operacao',
    'precificacao',
    'origem',
    'regras',
    'entrada',
    'mapeamento',
    'gerar_estoque',
    'preview',
    'download',
    'processar',
}
VALID_OPERATIONS = {'cadastro', 'estoque', 'universal', 'atualizacao_preco'}
VALID_ORIGINS = {'arquivo', 'site'}
VALID_ENTRY_CONTEXTS = {'bling_api', 'bling_csv', 'universal'}
STOCK_FORBIDDEN_STEPS = {'precificacao', 'mapeamento'}

LEGACY_WIDGET_PREFIXES = (
    'frontpage_origin_radio_',
    'cadastro_manual_mapping_',
    'estoque_manual_mapping_from_cadastro_',
)

CURRENT_WIDGET_PREFIXES = (
    'frontpage_origin_radio_cadastro',
    'frontpage_origin_radio_estoque',
    'frontpage_origin_radio_universal',
    'frontpage_origin_radio_atualizacao_preco',
    'cad_map_',
    'stk_map_',
    'bling_api_map_',
    'bling_csv_map_',
    'universal_map_',
    'urls_site_cadastro',
    'urls_site_estoque',
    'urls_site_universal',
    'urls_site_atualizacao_preco',
    'buscar_site_cadastro',
    'buscar_site_estoque',
    'buscar_site_universal',
    'buscar_site_atualizacao_preco',
    'origin_choose_file',
    'origin_choose_site',
)

DANGEROUS_LEGACY_KEYS = {
    'frontpage_origin_radio',
    'home_slim_active_panel',
    'origem_dados',
    'origem_tipo',
    'etapa_origem',
    'etapa_fluxo',
    'etapa',
}

SITE_RAW_BY_OPERATION = {
    'cadastro': 'df_site_bruto_cadastro',
    'estoque': 'df_site_bruto_estoque',
    'atualizacao_preco': 'df_site_bruto_atualizacao_preco',
}
SITE_INTERNAL_BY_OPERATION = {
    'cadastro': 'df_origem_site_como_planilha_cadastro',
    'estoque': 'df_origem_site_como_planilha_estoque',
    'atualizacao_preco': 'df_origem_site_como_planilha_atualizacao_preco',
}
SITE_OUTPUT_KEYS_BY_OPERATION = {
    'cadastro': [
        'df_final_cadastro',
        'mapping_cadastro',
        'mapping_confidence_cadastro',
        'df_origem_cadastro_precificada',
        'cadastro_wizard_df_origem',
        'cadastro_wizard_df_para_mapear',
        'cadastro_mapping_confirmed',
        'cadastro_mapping_confirmed_signature',
    ],
    'estoque': [
        'estoque_multi_outputs',
        'df_final_estoque',
        'mapping_estoque',
        'estoque_wizard_df_origem_site',
    ],
    'atualizacao_preco': [
        'df_final_atualizacao_preco',
        'mapping_atualizacao_preco',
        'mapping_confidence_atualizacao_preco',
    ],
}


def _is_legacy_widget_key(key: str) -> bool:
    if key in DANGEROUS_LEGACY_KEYS:
        return True
    if key.startswith(CURRENT_WIDGET_PREFIXES):
        return False
    return key.startswith(LEGACY_WIDGET_PREFIXES)


def _selected_operation() -> str:
    for value in (
        st.session_state.get(MODEL_CONTRACT_TYPE_KEY),
        st.session_state.get(FLOW_OPERATION_KEY),
        st.session_state.get('operacao_final'),
        st.session_state.get('tipo_operacao_final'),
        st.session_state.get('home_detected_operation'),
    ):
        operation = normalize_contract_operation(value)
        if operation in VALID_OPERATIONS:
            return operation
    return ''


def _normalize_entry_context() -> None:
    context = str(st.session_state.get(HOME_ENTRY_CONTEXT_KEY) or '').strip().lower()
    if context == 'bling':
        st.session_state[HOME_ENTRY_CONTEXT_KEY] = 'bling_api'
        return
    if context and context not in VALID_ENTRY_CONTEXTS:
        st.session_state.pop(HOME_ENTRY_CONTEXT_KEY, None)


def _normalize_scalar_state() -> None:
    _normalize_entry_context()

    step = str(st.session_state.get(WIZARD_STEP_KEY) or 'modelo').strip().lower()
    if step not in VALID_STEPS:
        step = 'modelo'
        st.session_state[WIZARD_STEP_KEY] = step

    operation = _selected_operation()
    if operation:
        st.session_state[FLOW_OPERATION_KEY] = operation
        st.session_state['operacao_final'] = operation
        st.session_state['tipo_operacao_final'] = operation
        st.session_state['home_detected_operation'] = operation
        if operation != 'universal':
            st.session_state[MODEL_CONTRACT_TYPE_KEY] = operation
    else:
        raw_operation = str(st.session_state.get(FLOW_OPERATION_KEY) or '').strip().lower()
        if raw_operation:
            st.session_state.pop(FLOW_OPERATION_KEY, None)
            st.session_state.pop('operacao_final', None)
            st.session_state.pop('tipo_operacao_final', None)

    operation = _selected_operation()
    if operation == 'estoque' and step in STOCK_FORBIDDEN_STEPS:
        st.session_state[WIZARD_STEP_KEY] = 'origem'

    origin = str(st.session_state.get(FLOW_ORIGIN_KEY) or '').strip().lower()
    if origin and origin not in VALID_ORIGINS:
        st.session_state.pop(FLOW_ORIGIN_KEY, None)
        st.session_state.pop('origem_final', None)
        st.session_state.pop('tipo_operacao_site', None)


def _clear_legacy_widgets() -> None:
    for key in list(st.session_state.keys()):
        text = str(key)
        if _is_legacy_widget_key(text):
            st.session_state.pop(text, None)


def _clear_cross_operation_site_state() -> None:
    operation = _selected_operation()
    if not operation or operation == 'universal':
        return
    others = [candidate for candidate in ('cadastro', 'estoque', 'atualizacao_preco') if candidate != operation]

    for other in others:
        for key in [
            SITE_RAW_BY_OPERATION.get(other, ''),
            SITE_INTERNAL_BY_OPERATION.get(other, ''),
            f'site_source_urls_como_planilha_{other}',
            f'site_requested_columns_como_planilha_{other}',
        ]:
            if key:
                st.session_state.pop(key, None)

        for key in SITE_OUTPUT_KEYS_BY_OPERATION.get(other, []):
            st.session_state.pop(key, None)

    legacy_operation = normalize_contract_operation(st.session_state.get('operation_site') or st.session_state.get('tipo_operacao_site'))
    if legacy_operation and legacy_operation != operation:
        st.session_state.pop('df_site_bruto', None)
        st.session_state.pop('operation_site', None)
        st.session_state.pop('tipo_operacao_site', None)


def _needs_heavy_cleanup(force: bool, operation: str) -> bool:
    if force:
        return True
    if st.session_state.get(STATE_GUARD_VERSION_KEY) != STATE_GUARD_VERSION:
        return True
    return bool(operation and operation != 'universal' and st.session_state.get(STATE_GUARD_LAST_OPERATION_KEY) != operation)


def run_wizard_state_guard(force: bool = False) -> None:
    """Guard rápido: limpeza pesada só quando necessário e sem apagar contrato real."""
    _normalize_scalar_state()
    operation = _selected_operation()
    if not _needs_heavy_cleanup(force, operation):
        return

    _clear_legacy_widgets()
    _clear_cross_operation_site_state()
    st.session_state[STATE_GUARD_VERSION_KEY] = STATE_GUARD_VERSION
    st.session_state[STATE_GUARD_LAST_OPERATION_KEY] = operation
