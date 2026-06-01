from __future__ import annotations

from typing import Callable

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.features_runtime.router import active_steps as runtime_active_steps
from bling_app_zero.features_runtime.router import feature_needs_model
from bling_app_zero.ui.home_wizard_constants import (
    CADASTRO_STEPS,
    ESTOQUE_STEPS,
    FLOW_OPERATION_KEY,
    FLOW_ORIGIN_KEY,
    GLOBAL_CADASTRO_MODEL_KEYS,
    GLOBAL_ESTOQUE_MODEL_KEYS,
    HOME_CADASTRO_MODEL_KEY,
    HOME_ESTOQUE_MODEL_KEY,
    RESET_OUTPUT_KEYS,
    STEP_ENTRADA,
    STEP_MODELO,
    STEP_OPERACAO,
    STEP_ORIGEM,
    WIZARD_STEP_KEY,
)
from bling_app_zero.ui.home_wizard_rerun import safe_rerun, set_step_without_rerun
from bling_app_zero.universal.model_contract_detector import MODEL_CONTRACT_TYPE_KEY, normalize_contract_operation

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard_state.py'
SINGLE_PAGE_FLOW = True
HOME_CHOICE_TARGET = '__home_choice__'
ORIGIN_RADIO_KEY = 'frontpage_origin_radio_universal'
QUICK_MODEL_READY_KEY = 'bling_quick_model_ready_origin'
UNIVERSAL_OPERATION = 'universal'
UNIVERSAL_REVIEW_OPERATION = 'modelo_destino'
UNIVERSAL_STEPS = [step for step in CADASTRO_STEPS if step != STEP_OPERACAO]
FINAL_CHECK_REPORT_KEY = 'home_wizard_final_check_report'
SAFE_FIX_SUGGESTIONS_KEY = 'home_wizard_safe_fix_suggestions'
FINAL_UNIVERSAL_KEY = 'df_final_universal'
FINAL_UNIVERSAL_LEGACY_KEY = 'df_final_cadastro'
SCROLL_TARGET_KEY = 'home_wizard_scroll_target_step'
STALE_CADASTRO_OPERATION_KEYS = (
    'df_final_download_operation',
    'df_final_preview_operation',
    'final_download_operation',
    'bling_wizard_state_guard_last_operation',
)


def _contract_operation() -> str:
    for value in (
        st.session_state.get(MODEL_CONTRACT_TYPE_KEY),
        st.session_state.get(FLOW_OPERATION_KEY),
        st.session_state.get('home_detected_operation'),
        st.session_state.get('operacao_final'),
        st.session_state.get('tipo_operacao_final'),
    ):
        operation = normalize_contract_operation(value)
        if operation:
            return operation
    return UNIVERSAL_OPERATION


def looks_like_loaded_df(value: object) -> bool:
    if value is None or not hasattr(value, 'columns'):
        return False
    try:
        return len(getattr(value, 'columns', [])) > 0
    except Exception:
        return False


def has_any_model(keys: list[str]) -> bool:
    return any(looks_like_loaded_df(st.session_state.get(key)) for key in keys)


def has_cadastro_model() -> bool:
    return has_any_model([HOME_CADASTRO_MODEL_KEY, *GLOBAL_CADASTRO_MODEL_KEYS])


def has_estoque_model() -> bool:
    return has_any_model([HOME_ESTOQUE_MODEL_KEY, *GLOBAL_ESTOQUE_MODEL_KEYS])


def has_preco_model() -> bool:
    return has_any_model(['home_modelo_atualizacao_preco_df', 'df_modelo_atualizacao_preco', 'modelo_atualizacao_preco_df'])


def has_universal_model() -> bool:
    return has_any_model(['home_modelo_universal_df', 'df_modelo_universal', 'modelo_universal_df'])


def has_home_models() -> bool:
    if not feature_needs_model():
        return True
    return has_cadastro_model() or has_estoque_model() or has_preco_model() or has_universal_model()


def came_from_bling_quick_model() -> bool:
    return bool(st.session_state.get(QUICK_MODEL_READY_KEY)) and has_home_models()


def query_param(name: str) -> str:
    try:
        value = st.query_params.get(name, '')
        if isinstance(value, list):
            return str(value[0] if value else '')
        return str(value or '')
    except Exception:
        return ''


def clear_stale_cadastro_operation_state() -> None:
    """Remove estados antigos que faziam o download universal aparecer como CADASTRO."""
    removed: list[str] = []
    current_contract = _contract_operation()
    for key in STALE_CADASTRO_OPERATION_KEYS:
        if str(st.session_state.get(key) or '').strip().lower() == 'cadastro' and current_contract != 'cadastro':
            st.session_state.pop(key, None)
            removed.append(key)

    widget_key = str(st.session_state.get('final_download_widget_key') or '')
    if current_contract != 'cadastro' and ('_cadastro_' in widget_key or widget_key.endswith('_cadastro')):
        st.session_state.pop('final_download_widget_key', None)
        removed.append('final_download_widget_key')

    for key in list(st.session_state.keys()):
        text_key = str(key)
        if current_contract != 'cadastro' and text_key.startswith('download_template_modelo_anexado_cadastro'):
            st.session_state.pop(key, None)
            removed.append(text_key)

    if removed:
        add_audit_event(
            'universal_flow_stale_cadastro_state_cleared',
            area='WIZARD',
            step='download',
            status='OK',
            details={'removed_keys': removed[:30], 'removed_count': len(removed), 'contract': current_contract, 'responsible_file': RESPONSIBLE_FILE},
        )


def ensure_universal_operation_state() -> str:
    if feature_needs_model() and not has_home_models():
        return ''
    operation = _contract_operation()
    clear_stale_cadastro_operation_state()
    st.session_state[FLOW_OPERATION_KEY] = operation
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state['home_detected_operation'] = operation
    st.session_state['home_slim_flow_operation'] = operation
    if operation != 'universal':
        st.session_state[MODEL_CONTRACT_TYPE_KEY] = operation
    st.session_state.pop('tipo_operacao_site', None)
    return operation


def selected_operation() -> str:
    return ensure_universal_operation_state()


def wizard_steps_for_operation(operation: str | None = None) -> list[str]:
    _ = operation
    steps = runtime_active_steps()
    if not feature_needs_model():
        return [step for step in steps if step != STEP_MODELO]
    return list(steps) if has_home_models() else [STEP_MODELO]


def target_by_delta(current_step: str, operation: str, delta: int) -> str:
    steps = wizard_steps_for_operation(operation)
    current = str(current_step or '').strip().lower()
    if current == STEP_OPERACAO:
        current = STEP_ORIGEM
    if current not in steps:
        return steps[0]
    index = steps.index(current)
    return steps[max(0, min(len(steps) - 1, index + delta))]


def wizard_previous_target(current_step: str, operation: str) -> str:
    return target_by_delta(current_step, operation, -1)


def wizard_next_target(current_step: str, operation: str) -> str:
    return target_by_delta(current_step, operation, 1)


def normalize_origin_value(value: object) -> str:
    text = str(value or '').strip().lower()
    if text in {'arquivo', 'site'}:
        return text
    if any(item in text for item in ('arquivo', 'planilha', 'xml', 'pdf')):
        return 'arquivo'
    if 'site' in text:
        return 'site'
    return ''


def current_origin_choice() -> str:
    current = normalize_origin_value(st.session_state.get(FLOW_ORIGIN_KEY))
    if current:
        return current
    radio_origin = normalize_origin_value(st.session_state.get(ORIGIN_RADIO_KEY))
    if radio_origin:
        return radio_origin
    origem = normalize_origin_value(query_param('origem') or query_param('flow'))
    return origem


def _set_scroll_target_safe(set_scroll_target: Callable[[str], None] | None, target_step: str) -> bool:
    """Define o alvo de rolagem mesmo quando o chamador não envia callback."""
    if callable(set_scroll_target):
        set_scroll_target(target_step)
        return True
    st.session_state[SCROLL_TARGET_KEY] = target_step
    return False


def select_origin(origin: str, *, set_scroll_target: Callable[[str], None] | None = None) -> None:
    origin = normalize_origin_value(origin)
    if origin not in {'arquivo', 'site'}:
        return
    previous_origin = st.session_state.get(FLOW_ORIGIN_KEY)
    operation = _contract_operation()
    st.session_state[ORIGIN_RADIO_KEY] = origin
    st.session_state[FLOW_ORIGIN_KEY] = origin
    st.session_state[FLOW_OPERATION_KEY] = operation
    st.session_state['operacao_final'] = operation
    st.session_state['tipo_operacao_final'] = operation
    st.session_state['origem_final'] = origin
    st.session_state.pop('tipo_operacao_site', None)
    st.session_state['home_slim_flow_operation'] = operation
    if operation != 'universal':
        st.session_state[MODEL_CONTRACT_TYPE_KEY] = operation
    clear_stale_cadastro_operation_state()
    set_step_without_rerun(STEP_ENTRADA)
    scroll_callback_used = _set_scroll_target_safe(set_scroll_target, STEP_ENTRADA)
    add_audit_event(
        'single_page_origin_selected',
        area='WIZARD',
        step=STEP_ORIGEM,
        details={
            'origin': origin,
            'operation': operation,
            'previous_origin': previous_origin,
            'scroll_target': STEP_ENTRADA,
            'scroll_callback_used': scroll_callback_used,
            'single_page_flow': SINGLE_PAGE_FLOW,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    try:
        st.query_params['origem'] = origin
        st.query_params['flow'] = 'site' if origin == 'site' else 'arquivo'
        st.query_params['step'] = STEP_ENTRADA
        st.query_params['operacao'] = operation
        st.query_params['operation'] = operation
    except Exception:
        pass
    safe_rerun('origin_selected', target_step=STEP_ENTRADA)


def reset_wizard() -> None:
    for key in RESET_OUTPUT_KEYS:
        st.session_state.pop(key, None)
    st.session_state.pop(FLOW_ORIGIN_KEY, None)
    st.session_state.pop('origem_final', None)
    st.session_state.pop(QUICK_MODEL_READY_KEY, None)
    add_audit_event('wizard_reset', area='WIZARD', step='download', details={'single_page_flow': SINGLE_PAGE_FLOW, 'responsible_file': RESPONSIBLE_FILE})
    safe_rerun('wizard_reset', target_step=STEP_MODELO)


def get_df_final_universal():
    current = st.session_state.get(FINAL_UNIVERSAL_KEY)
    if looks_like_loaded_df(current):
        return current
    return st.session_state.get(FINAL_UNIVERSAL_LEGACY_KEY)


def set_df_final_universal(df_final: object) -> None:
    if not looks_like_loaded_df(df_final):
        return
    st.session_state[FINAL_UNIVERSAL_KEY] = df_final
    st.session_state[FINAL_UNIVERSAL_LEGACY_KEY] = df_final
    st.session_state.pop('df_final_cadastro_preview_rules_applied', None)
    st.session_state.pop(FINAL_CHECK_REPORT_KEY, None)


__all__ = [
    'FINAL_CHECK_REPORT_KEY',
    'HOME_CHOICE_TARGET',
    'SAFE_FIX_SUGGESTIONS_KEY',
    'SINGLE_PAGE_FLOW',
    'UNIVERSAL_OPERATION',
    'UNIVERSAL_REVIEW_OPERATION',
    'came_from_bling_quick_model',
    'clear_stale_cadastro_operation_state',
    'current_origin_choice',
    'ensure_universal_operation_state',
    'get_df_final_universal',
    'has_home_models',
    'looks_like_loaded_df',
    'query_param',
    'reset_wizard',
    'select_origin',
    'selected_operation',
    'set_df_final_universal',
    'wizard_next_target',
    'wizard_previous_target',
    'wizard_steps_for_operation',
]
