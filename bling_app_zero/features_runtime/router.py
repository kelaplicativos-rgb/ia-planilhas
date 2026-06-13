from __future__ import annotations

import streamlit as st
from streamlit.errors import StreamlitAPIException

from bling_app_zero.features_runtime.contracts import FeatureContract
from bling_app_zero.features_runtime.registry import get_feature_contract

HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
FINISH_MODE_KEY = 'bling_finish_mode'
UNIFIED_BLING_SEND_KEY = 'home_bling_connected_same_flow_api_send'
WIZARD_STEP_KEY = 'bling_wizard_step'

API_CONTEXTS = {'bling', 'bling_api', 'api', 'api_direct'}
API_FINISH_MODES = {'api_direct', 'api', 'bling_api'}
SOURCE_FIRST_STEPS = {'origem', 'entrada'}
SOURCE_DF_KEYS = (
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


def _clean(value: object) -> str:
    return str(value or '').strip().lower()


def _safe_state_set(key: str, value: object) -> None:
    try:
        st.session_state[key] = value
    except StreamlitAPIException:
        st.session_state.setdefault('flow_spine_widget_state_warnings', {})[key] = str(value)
    except Exception:
        pass


def _looks_like_loaded_df(value: object) -> bool:
    try:
        return bool(value is not None and not value.empty and len(value.columns) > 0)
    except Exception:
        return False


def _source_data_ready() -> bool:
    for key in SOURCE_DF_KEYS:
        if _looks_like_loaded_df(st.session_state.get(key)):
            return True
    try:
        from bling_app_zero.ui.universal_wizard_state import universal_context_ready

        return bool(universal_context_ready())
    except Exception:
        return False


def active_mode() -> str:
    # BLINGFIX 2026-06-13:
    # Quando o Bling está conectado no fluxo unificado, só o destino final vira API.
    # O contrato do wizard precisa continuar CSV/universal para não abrir o fluxo curto.
    if bool(st.session_state.get(UNIFIED_BLING_SEND_KEY)):
        return 'csv'
    context = _clean(st.session_state.get(HOME_ENTRY_CONTEXT_KEY))
    finish = _clean(st.session_state.get(FINISH_MODE_KEY))
    destination = _clean(st.session_state.get('flow_spine_final_destination'))
    if finish in API_FINISH_MODES or context in API_CONTEXTS or destination == 'api_bling':
        return 'api'
    return 'csv'


def active_operation() -> str:
    # Para arquivos/planilhas/download, não existe mais contrato interno por tipo.
    # O modelo anexado pelo usuário é o contrato universal absoluto.
    if active_mode() != 'api':
        return 'universal'
    return 'universal'


def _apply_runtime_state(contract: FeatureContract) -> None:
    _safe_state_set('active_feature_contract_key', 'universal_mapping')
    _safe_state_set('active_feature_operation', 'universal')
    _safe_state_set('active_feature_mode', contract.mode)
    _safe_state_set('active_feature_steps', list(contract.steps))
    _safe_state_set('flow_spine_contract_key', 'universal_mapping')
    _safe_state_set('flow_spine_operation', 'universal')
    _safe_state_set('flow_spine_primary_action_label', 'Download Modelo Mapeado')
    if contract.mode == 'api':
        _safe_state_set('flow_spine_final_destination', 'api_bling')
        _safe_state_set('flow_spine_final_title', 'Enviar')
        _safe_state_set('direct_bling_operation_applied', 'universal')
    else:
        _safe_state_set('flow_spine_final_destination', 'download')
        _safe_state_set('flow_spine_final_title', 'Download')


def active_contract() -> FeatureContract:
    mode = active_mode()
    contract = get_feature_contract('universal', mode)
    _apply_runtime_state(contract)
    return contract


def active_steps() -> list[str]:
    return list(active_contract().steps)


def step_allowed(step: str) -> bool:
    return str(step or '').strip().lower() in active_steps()


def feature_needs_model() -> bool:
    contract = active_contract()
    if not contract.needs_model:
        return False

    # BLINGSCAN 2026-06-13:
    # No fluxo origem-primeiro, modelo não pode bloquear Origem/Dados.
    # Ele passa a ser obrigatório depois que a origem realmente gerou dados.
    current_step = _clean(st.session_state.get(WIZARD_STEP_KEY))
    if current_step in SOURCE_FIRST_STEPS and not _source_data_ready():
        return False
    return True


def feature_needs_pricing() -> bool:
    return active_contract().needs_pricing


def feature_needs_mapping() -> bool:
    return active_contract().needs_mapping


def feature_needs_rules_review() -> bool:
    return active_contract().needs_rules_review


def feature_needs_download() -> bool:
    return active_contract().needs_download


def feature_primary_action_label() -> str:
    return 'Download Modelo Mapeado'


__all__ = [
    'active_contract',
    'active_mode',
    'active_operation',
    'active_steps',
    'feature_needs_download',
    'feature_needs_mapping',
    'feature_needs_model',
    'feature_needs_pricing',
    'feature_needs_rules_review',
    'feature_primary_action_label',
    'step_allowed',
]
