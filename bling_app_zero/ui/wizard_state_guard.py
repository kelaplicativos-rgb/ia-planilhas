from __future__ import annotations

import streamlit as st

WIZARD_STEP_KEY = 'bling_wizard_step'
FLOW_OPERATION_KEY = 'home_slim_flow_operation'
FLOW_ORIGIN_KEY = 'home_slim_flow_origin'
STATE_GUARD_VERSION_KEY = 'bling_wizard_state_guard_version'
STATE_GUARD_VERSION = '2026-05-12-wizard-regras-guard-1'

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
VALID_OPERATIONS = {'cadastro', 'estoque'}
VALID_ORIGINS = {'arquivo', 'site'}

LEGACY_WIDGET_PREFIXES = (
    'frontpage_origin_radio_',
    'cadastro_manual_mapping_',
    'estoque_manual_mapping_from_cadastro_',
)

CURRENT_WIDGET_PREFIXES = (
    'frontpage_origin_radio_cadastro',
    'frontpage_origin_radio_estoque',
    'cad_map_',
    'stk_map_',
    'urls_site_cadastro',
    'urls_site_estoque',
    'buscar_site_cadastro',
    'buscar_site_estoque',
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
}
SITE_INTERNAL_BY_OPERATION = {
    'cadastro': 'df_origem_site_como_planilha_cadastro',
    'estoque': 'df_origem_site_como_planilha_estoque',
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
}


def _is_legacy_widget_key(key: str) -> bool:
    if key in DANGEROUS_LEGACY_KEYS:
        return True
    if key.startswith(CURRENT_WIDGET_PREFIXES):
        return False
    return key.startswith(LEGACY_WIDGET_PREFIXES)


def _selected_operation() -> str:
    operation = str(st.session_state.get(FLOW_OPERATION_KEY) or st.session_state.get('operacao_final') or '').strip().lower()
    return operation if operation in VALID_OPERATIONS else ''


def _normalize_scalar_state() -> None:
    step = str(st.session_state.get(WIZARD_STEP_KEY) or 'modelo').strip().lower()
    if step not in VALID_STEPS:
        st.session_state[WIZARD_STEP_KEY] = 'modelo'

    operation = _selected_operation()
    if operation:
        st.session_state[FLOW_OPERATION_KEY] = operation
        st.session_state['operacao_final'] = operation
        st.session_state['tipo_operacao_final'] = operation
    else:
        raw_operation = str(st.session_state.get(FLOW_OPERATION_KEY) or '').strip().lower()
        if raw_operation:
            st.session_state.pop(FLOW_OPERATION_KEY, None)
            st.session_state.pop('operacao_final', None)
            st.session_state.pop('tipo_operacao_final', None)

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
    if not operation:
        return
    other = 'estoque' if operation == 'cadastro' else 'cadastro'

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

    legacy_operation = str(st.session_state.get('operation_site') or st.session_state.get('tipo_operacao_site') or '').strip().lower()
    if legacy_operation and legacy_operation != operation:
        st.session_state.pop('df_site_bruto', None)
        st.session_state.pop('operation_site', None)
        st.session_state.pop('tipo_operacao_site', None)


def run_wizard_state_guard(force: bool = False) -> None:
    """Limpa estados antigos que quebram widgets dinâmicos do Streamlit.

    Preserva dados importantes do fluxo atual e remove resultados cruzados entre
    cadastro e estoque, principalmente origem por site salva com operação antiga.
    A etapa ``regras`` é uma etapa oficial do wizard e nunca deve ser normalizada
    para ``modelo`` pelo guard.
    """
    current_version = st.session_state.get(STATE_GUARD_VERSION_KEY)
    if force or current_version != STATE_GUARD_VERSION:
        _clear_legacy_widgets()
        st.session_state[STATE_GUARD_VERSION_KEY] = STATE_GUARD_VERSION
    _normalize_scalar_state()
    _clear_cross_operation_site_state()
