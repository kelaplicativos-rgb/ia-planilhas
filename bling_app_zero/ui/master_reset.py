from __future__ import annotations

from typing import Any, MutableMapping

import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/master_reset.py'

RESET_EXACT_KEYS = {
    'home_active_operation_v2',
    'home_allow_operation_v2_session',
    'home_boot_landing_rendered_once',
    'home_single_page_flow_active',
    'home_entry_context',
    'home_slim_entry_context',
    'home_slim_flow_origin',
    'home_slim_flow_operation',
    'home_detected_operation',
    'home_bling_connected_same_flow_api_send',
    'bling_finish_mode',
    'finish_mode',
    'skip_direct_bling_connection_this_flow',
    'bling_wizard_step',
    'home_wizard_step',
    'neutral_wizard_state_v1',
    'home_wizard_last_rerun_reason',
    'home_wizard_last_rerun_target',
    'home_wizard_scroll_target_step',
    'frontpage_origin_radio',
    'frontpage_origin_radio_universal',
    'origem_final',
    'origem_dados',
    'origem_tipo',
    'tipo_operacao',
    'operacao_final',
    'tipo_operacao_final',
    'destination_model_contract_type',
    'destination_model_contract_label',
    'destination_model_upload_bytes',
    'destination_model_upload_name',
    'destination_model_upload_signature',
    'home_modelo_cadastro_df',
    'home_modelo_estoque_df',
    'home_modelo_universal_df',
    'home_modelo_atualizacao_preco_df',
    'df_modelo_cadastro',
    'modelo_cadastro_df',
    'df_modelo_estoque',
    'modelo_estoque_df',
    'df_modelo_universal',
    'modelo_universal_df',
    'df_modelo_atualizacao_preco',
    'modelo_atualizacao_preco_df',
    'cadastro_wizard_df_origem',
    'cadastro_wizard_df_para_mapear',
    'cadastro_wizard_df_modelo',
    'cadastro_wizard_df_modelo_estoque',
    'cadastro_mapping_confirmed',
    'cadastro_mapping_confirmed_signature',
    'df_origem',
    'df_origem_planilha',
    'df_produtos_origem',
    'df_origem_cadastro_precificada',
    'df_final_universal',
    'df_final_cadastro',
    'df_final_estoque',
    'df_final_download_snapshot',
    'df_final_cadastro_preview_rules_applied',
    'home_pricing_config',
    'home_pricing_enabled_toggle',
    'home_precificacao_inicial',
    'cadastro_preco_calculado_ativo',
    'price_calculator_source_cost_column',
    'global_price_source_cost_column',
    'price_calculator_config',
    'global_price_config',
    'price_calculator_ready',
    'global_price_ready',
    'bling_user_rules',
    'rules_center_reviewed',
    'rules_center_ready',
    'universal_preview_report',
    'flow_spine_preview_ready',
}

RESET_PREFIXES = (
    'df_final_',
    'df_origem_',
    'df_modelo_',
    'modelo_',
    'mapping_',
    'cadastro_',
    'estoque_',
    'site_',
    'df_site_',
    'blingsmartscan_',
    'destination_model_',
    'home_modelo_',
    'home_pricing_',
    'price_calculator_',
    'global_price_',
    'easy_price_',
    'rules_center_',
    'flow_spine_',
    'active_feature_',
    'direct_bling_operation_',
    'wizard_manual_',
    'bling_autofluxo_',
    'universal_map_',
    'mapping_page_',
)

REUSABLE_ORIGIN_KEYS = (
    'cadastro_wizard_df_origem',
    'df_origem',
    'df_origem_planilha',
    'df_produtos_origem',
    'df_origem_site',
    'df_origem_site_como_planilha',
    'df_origem_site_como_planilha_universal',
    'df_origem_site_como_planilha_cadastro',
    'df_origem_site_como_planilha_estoque',
    'df_origem_site_como_planilha_atualizacao_preco',
    'df_origem_cadastro',
    'df_origem_estoque',
    'df_origem_universal',
    'df_site_bruto',
    'df_site_bruto_universal',
    'df_site_bruto_cadastro',
    'df_site_bruto_estoque',
    'df_site_bruto_atualizacao_preco',
    'estoque_wizard_df_origem_site',
)


def _valid_origin_data(value: object) -> bool:
    if value is None or not hasattr(value, 'columns'):
        return False
    try:
        return len(value) > 0 and len(getattr(value, 'columns', [])) > 0
    except Exception:
        return False


def reusable_origin_key(state: MutableMapping[str, Any]) -> str:
    for key in REUSABLE_ORIGIN_KEYS:
        if _valid_origin_data(state.get(key)):
            return key
    return ''


def reusable_origin_available(state: MutableMapping[str, Any]) -> bool:
    return bool(reusable_origin_key(state))


def should_clear_for_new_operation(key: object) -> bool:
    text = str(key or '')
    return text in RESET_EXACT_KEYS or any(text.startswith(prefix) for prefix in RESET_PREFIXES)


def clear_operation_state(state: MutableMapping[str, Any]) -> list[str]:
    removed: list[str] = []
    for key in list(state.keys()):
        if should_clear_for_new_operation(key):
            state.pop(key, None)
            removed.append(str(key))
    return removed


def prepare_reuse_origin_state(state: MutableMapping[str, Any]) -> tuple[str, list[str]]:
    source_key = reusable_origin_key(state)
    if not source_key:
        return '', []

    source_data = state.get(source_key)
    source_kind = str(
        state.get('home_slim_flow_origin')
        or state.get('frontpage_origin_radio_universal')
        or state.get('origem_final')
        or ('site' if 'site' in source_key else 'arquivo')
    ).strip().lower()
    if source_kind not in {'arquivo', 'site'}:
        source_kind = 'site' if 'site' in source_key else 'arquivo'

    api_send = bool(state.get('home_bling_connected_same_flow_api_send'))
    removed = clear_operation_state(state)

    state['cadastro_wizard_df_origem'] = source_data
    state['home_slim_flow_origin'] = source_kind
    state['frontpage_origin_radio_universal'] = source_kind
    state['origem_final'] = source_kind
    state['home_active_operation_v2'] = 'wizard_cadastro_estoque'
    state['home_allow_operation_v2_session'] = True
    state['home_single_page_flow_active'] = True
    state['home_entry_context'] = 'universal'
    state['bling_finish_mode'] = 'csv_download'
    state['finish_mode'] = 'csv_download'
    state['skip_direct_bling_connection_this_flow'] = True
    state['bling_wizard_step'] = 'modelo'
    state['home_wizard_step'] = 'modelo'
    if api_send:
        state['home_bling_connected_same_flow_api_send'] = True

    return source_key, removed


def clear_navigation_params() -> None:
    try:
        for key in ('operation_v2', 'step', 'flow', 'origem', 'operacao', 'operation', 'mapping_page', 'page'):
            st.query_params.pop(key, None)
    except Exception:
        pass


def _set_reuse_navigation_params(source_kind: str) -> None:
    clear_navigation_params()
    try:
        st.query_params['operation_v2'] = 'wizard_cadastro_estoque'
        st.query_params['step'] = 'modelo'
        st.query_params['origem'] = source_kind
        st.query_params['flow'] = 'site' if source_kind == 'site' else 'arquivo'
    except Exception:
        pass


def master_reset_to_home() -> list[str]:
    removed = clear_operation_state(st.session_state)
    st.session_state['home_active_operation_v2'] = 'home'
    st.session_state['home_allow_operation_v2_session'] = False
    st.session_state['home_single_page_flow_active'] = False
    clear_navigation_params()
    add_audit_event(
        'master_reset_new_operation',
        area='HOME',
        step='home',
        status='OK',
        details={
            'removed_count': len(removed),
            'removed_keys': removed[:120],
            'bling_connection_preserved': True,
            'navigation_history_cleared': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return removed


def reuse_origin_for_new_operation() -> bool:
    source_key, removed = prepare_reuse_origin_state(st.session_state)
    if not source_key:
        return False
    source_kind = str(st.session_state.get('home_slim_flow_origin') or 'arquivo')
    _set_reuse_navigation_params(source_kind)
    add_audit_event(
        'reuse_origin_for_new_operation',
        area='HOME',
        step='modelo',
        status='OK',
        details={
            'source_key': source_key,
            'source_kind': source_kind,
            'removed_count': len(removed),
            'removed_keys': removed[:120],
            'origin_preserved': True,
            'previous_outputs_cleared': True,
            'bling_connection_preserved': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return True


__all__ = [
    'RESET_EXACT_KEYS',
    'RESET_PREFIXES',
    'REUSABLE_ORIGIN_KEYS',
    'clear_navigation_params',
    'clear_operation_state',
    'master_reset_to_home',
    'prepare_reuse_origin_state',
    'reusable_origin_available',
    'reusable_origin_key',
    'reuse_origin_for_new_operation',
    'should_clear_for_new_operation',
]
