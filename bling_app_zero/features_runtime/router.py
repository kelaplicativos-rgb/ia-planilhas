from __future__ import annotations

import streamlit as st

from bling_app_zero.features_runtime.contracts import FeatureContract
from bling_app_zero.features_runtime.registry import get_feature_contract

HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
FINISH_MODE_KEY = 'bling_finish_mode'
MODEL_CONTRACT_TYPE_KEY = 'model_contract_type'


def _first_state_value(*keys: str) -> object:
    for key in keys:
        value = st.session_state.get(key)
        if value not in (None, ''):
            return value
    return ''


def active_operation() -> str:
    return str(
        _first_state_value(
            MODEL_CONTRACT_TYPE_KEY,
            'home_slim_flow_operation',
            'home_detected_operation',
            'operacao_final',
            'tipo_operacao_final',
            'tipo_operacao_site',
            'operation_site',
            'direct_bling_operation_choice',
        )
        or ''
    )


def active_mode() -> str:
    context = str(st.session_state.get(HOME_ENTRY_CONTEXT_KEY) or '').strip().lower()
    finish = str(st.session_state.get(FINISH_MODE_KEY) or '').strip().lower()
    if context in {'bling', 'bling_api'} or finish == 'api_direct':
        return 'api'
    return 'csv'


def active_contract() -> FeatureContract:
    contract = get_feature_contract(active_operation(), active_mode())
    st.session_state['active_feature_contract_key'] = contract.key
    st.session_state['active_feature_operation'] = contract.operation
    st.session_state['active_feature_mode'] = contract.mode
    st.session_state['active_feature_steps'] = list(contract.steps)
    return contract


def active_steps() -> list[str]:
    return list(active_contract().steps)


def step_allowed(step: str) -> bool:
    return str(step or '').strip().lower() in active_steps()


def feature_needs_model() -> bool:
    return active_contract().needs_model


def feature_needs_pricing() -> bool:
    return active_contract().needs_pricing


def feature_needs_mapping() -> bool:
    return active_contract().needs_mapping


def feature_needs_rules_review() -> bool:
    return active_contract().needs_rules_review


def feature_needs_download() -> bool:
    return active_contract().needs_download


def feature_primary_action_label() -> str:
    return active_contract().primary_action_label


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
