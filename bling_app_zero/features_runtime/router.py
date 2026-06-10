from __future__ import annotations

import streamlit as st
from streamlit.errors import StreamlitAPIException

from bling_app_zero.features_runtime.contracts import FeatureContract
from bling_app_zero.features_runtime.registry import get_feature_contract, normalize_operation
from bling_app_zero.universal.model_contract_detector import MODEL_CONTRACT_TYPE_KEY as DESTINATION_MODEL_CONTRACT_TYPE_KEY

HOME_ENTRY_CONTEXT_KEY = 'home_entry_context'
FINISH_MODE_KEY = 'bling_finish_mode'
LEGACY_MODEL_CONTRACT_TYPE_KEY = 'model_contract_type'

API_CONTEXTS = {'bling', 'bling_api', 'api', 'api_direct'}
API_FINISH_MODES = {'api_direct', 'api', 'bling_api'}
API_OPERATION_PRIORITY_KEYS = (
    'site_capture_operation',
    'blingsmartscan_finished_operation',
    'direct_bling_operation_applied',
    'direct_bling_operation_choice',
    'flow_spine_api_batch_operation',
    DESTINATION_MODEL_CONTRACT_TYPE_KEY,
    'home_slim_flow_operation',
    'home_detected_operation',
    'operacao_final',
    'tipo_operacao_final',
    'flow_spine_operation',
    'active_feature_operation',
    'tipo_operacao_site',
    'operation_site',
    LEGACY_MODEL_CONTRACT_TYPE_KEY,
)
CSV_OPERATION_PRIORITY_KEYS = (
    DESTINATION_MODEL_CONTRACT_TYPE_KEY,
    'home_slim_flow_operation',
    'home_detected_operation',
    'operacao_final',
    'tipo_operacao_final',
    'tipo_operacao_site',
    'operation_site',
    'site_capture_operation',
    'blingsmartscan_finished_operation',
    'flow_spine_operation',
    'active_feature_operation',
    LEGACY_MODEL_CONTRACT_TYPE_KEY,
)


def _first_state_value(*keys: str) -> object:
    for key in keys:
        value = st.session_state.get(key)
        if value not in (None, ''):
            return value
    return ''


def _clean(value: object) -> str:
    return str(value or '').strip().lower()


def _safe_state_set(key: str, value: object) -> None:
    """Atualiza session_state sem quebrar quando a chave pertence a widget já criado.

    Streamlit não permite modificar st.session_state de um widget depois que ele
    foi instanciado na mesma execução. Isso acontecia com
    direct_bling_operation_choice. A regra aqui é: chaves internas podem ser
    forçadas; chaves de widget devem ser preservadas quando já estiverem
    bloqueadas pelo ciclo atual da tela.
    """
    try:
        st.session_state[key] = value
    except StreamlitAPIException:
        st.session_state.setdefault('flow_spine_widget_state_warnings', {})[key] = str(value)
    except Exception:
        pass


def active_mode() -> str:
    context = _clean(st.session_state.get(HOME_ENTRY_CONTEXT_KEY))
    finish = _clean(st.session_state.get(FINISH_MODE_KEY))
    destination = _clean(st.session_state.get('flow_spine_final_destination'))
    if finish in API_FINISH_MODES or context in API_CONTEXTS or destination == 'api_bling':
        return 'api'
    return 'csv'


def active_operation() -> str:
    keys = API_OPERATION_PRIORITY_KEYS if active_mode() == 'api' else CSV_OPERATION_PRIORITY_KEYS
    for key in keys:
        value = st.session_state.get(key)
        if value in (None, ''):
            continue
        operation = normalize_operation(value)
        if operation:
            if active_mode() == 'api' and operation == 'universal':
                continue
            return operation
    return 'cadastro' if active_mode() == 'api' else 'universal'


def _apply_runtime_state(contract: FeatureContract) -> None:
    _safe_state_set('active_feature_contract_key', contract.key)
    _safe_state_set('active_feature_operation', contract.operation)
    _safe_state_set('active_feature_mode', contract.mode)
    _safe_state_set('active_feature_steps', list(contract.steps))
    _safe_state_set('flow_spine_contract_key', contract.key)
    _safe_state_set('flow_spine_operation', contract.operation)
    _safe_state_set('flow_spine_primary_action_label', contract.primary_action_label)
    if contract.mode == 'api':
        _safe_state_set('flow_spine_final_destination', 'api_bling')
        _safe_state_set('flow_spine_final_title', 'Enviar para o Bling')
        _safe_state_set('direct_bling_operation_applied', contract.operation)
        _safe_state_set('bling_finish_mode', 'api_direct')
        _safe_state_set('home_entry_context', 'bling_api')
    else:
        _safe_state_set('flow_spine_final_destination', 'download')
        _safe_state_set('flow_spine_final_title', 'Baixar arquivo final')


def active_contract() -> FeatureContract:
    contract = get_feature_contract(active_operation(), active_mode())
    _apply_runtime_state(contract)
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
