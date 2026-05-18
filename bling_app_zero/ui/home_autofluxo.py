from __future__ import annotations

from typing import Any

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.ui.cadastro_wizard_state import cadastro_context_ready
from bling_app_zero.ui.estoque_wizard_state import estoque_context_ready
from bling_app_zero.ui.home_wizard_constants import (
    CADASTRO_STEPS,
    ESTOQUE_STEPS,
    FLOW_OPERATION_KEY,
    FLOW_ORIGIN_KEY,
    GLOBAL_CADASTRO_MODEL_KEYS,
    GLOBAL_ESTOQUE_MODEL_KEYS,
    HOME_CADASTRO_MODEL_KEY,
    HOME_ESTOQUE_MODEL_KEY,
    STEP_DOWNLOAD,
    STEP_ENTRADA,
    STEP_GERAR_ESTOQUE,
    STEP_MAPEAMENTO,
    STEP_MODELO,
    STEP_OPERACAO,
    STEP_ORIGEM,
    STEP_PRECIFICACAO,
    STEP_PREVIEW,
    STEP_REGRAS,
    WIZARD_STEP_KEY,
)
from bling_app_zero.ui.rules_center_step import rules_center_ready

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_autofluxo.py'
HOME_ACTIVE_OPERATION_KEY = 'home_active_operation_v2'
HOME_ALLOW_OPERATION_KEY = 'home_allow_operation_v2_session'
FLOW_WIZARD_VALUE = 'wizard_cadastro_estoque'
AUTOFLOW_ENABLED_KEY = 'bling_autofluxo_enabled'
AUTOFLOW_LAST_STEP_KEY = 'bling_autofluxo_last_step'
AUTOFLOW_PAUSE_STEP_KEY = 'bling_autofluxo_pause_step'
AUTOFLOW_LAST_MOVE_KEY = 'bling_autofluxo_last_move'
AUTOFLOW_MANUAL_LOCK_KEY = 'bling_autofluxo_manual_navigation_lock'
MANUAL_REVIEW_STEPS = {STEP_MAPEAMENTO, STEP_GERAR_ESTOQUE}


def _looks_like_loaded_df(value: Any) -> bool:
    if value is None or not hasattr(value, 'columns'):
        return False
    try:
        return len(getattr(value, 'columns', [])) > 0
    except Exception:
        return False


def _has_any_model(keys: list[str]) -> bool:
    return any(_looks_like_loaded_df(st.session_state.get(key)) for key in keys)


def _has_cadastro_model() -> bool:
    return _has_any_model([HOME_CADASTRO_MODEL_KEY, *GLOBAL_CADASTRO_MODEL_KEYS])


def _has_estoque_model() -> bool:
    return _has_any_model([HOME_ESTOQUE_MODEL_KEY, *GLOBAL_ESTOQUE_MODEL_KEYS])


def _has_home_model() -> bool:
    return _has_cadastro_model() or _has_estoque_model()


def _available_operations() -> list[str]:
    operations: list[str] = []
    if _has_cadastro_model():
        operations.append('cadastro')
    if _has_estoque_model():
        operations.append('estoque')
    return operations


def _sync_operation_from_model() -> str:
    available = _available_operations()
    current = str(st.session_state.get(FLOW_OPERATION_KEY) or '').strip().lower()

    if not available:
        return ''

    if current not in available:
        current = available[0]
        st.session_state[FLOW_OPERATION_KEY] = current
        st.session_state['operacao_final'] = current
        st.session_state['tipo_operacao_final'] = current
        add_audit_event(
            'autofluxo_operation_selected',
            area='AUTOFLOW',
            step=st.session_state.get(WIZARD_STEP_KEY),
            details={
                'operation': current,
                'available': available,
                'reason': 'model_detected_operation',
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
    return current


def _active_steps() -> list[str]:
    return ESTOQUE_STEPS if _sync_operation_from_model() == 'estoque' else CADASTRO_STEPS


def _current_step() -> str:
    steps = _active_steps()
    current = str(st.session_state.get(WIZARD_STEP_KEY) or STEP_MODELO).strip().lower()
    if not _has_home_model():
        current = STEP_MODELO
    elif current not in steps:
        current = STEP_MODELO
    st.session_state[WIZARD_STEP_KEY] = current
    return current


def _current_origin() -> str:
    origin = str(st.session_state.get(FLOW_ORIGIN_KEY) or '').strip().lower()
    if origin in {'arquivo', 'site'}:
        return origin
    origin_final = str(st.session_state.get('origem_final') or '').strip().lower()
    if origin_final in {'arquivo', 'site'}:
        return origin_final
    return ''


def _pricing_is_active() -> bool:
    if bool(st.session_state.get('home_precificacao_inicial')):
        return True
    if bool(st.session_state.get('home_pricing_enabled_toggle')):
        return True
    config = st.session_state.get('home_pricing_config')
    return isinstance(config, dict) and bool(config)


def _step_ready_for_autonext(step: str, operation: str) -> bool:
    if step == STEP_MODELO:
        return _has_home_model()
    if step == STEP_OPERACAO:
        return operation in {'cadastro', 'estoque'}
    if step == STEP_PRECIFICACAO:
        return operation == 'cadastro' and not _pricing_is_active()
    if step == STEP_ORIGEM:
        return _current_origin() in {'arquivo', 'site'}
    if step == STEP_ENTRADA:
        return estoque_context_ready() if operation == 'estoque' else cadastro_context_ready()
    if step in MANUAL_REVIEW_STEPS:
        return False
    if step == STEP_REGRAS:
        return rules_center_ready()
    return False


def _next_step_for(step: str, operation: str) -> str:
    steps = ESTOQUE_STEPS if operation == 'estoque' else CADASTRO_STEPS
    if step in {STEP_PREVIEW, STEP_DOWNLOAD}:
        return step
    if step not in steps:
        return STEP_MODELO
    index = steps.index(step)
    if index >= len(steps) - 1:
        return step
    return steps[index + 1]


def _remember_direction_and_respect_back_navigation(current: str) -> bool:
    steps = _active_steps()
    previous = str(st.session_state.get(AUTOFLOW_LAST_STEP_KEY) or '').strip().lower()
    st.session_state[AUTOFLOW_LAST_STEP_KEY] = current

    if not previous or previous not in steps or current not in steps:
        return False

    previous_index = steps.index(previous)
    current_index = steps.index(current)
    if current_index < previous_index:
        st.session_state[AUTOFLOW_PAUSE_STEP_KEY] = current
        add_audit_event(
            'autofluxo_paused_after_back',
            area='AUTOFLOW',
            step=current,
            details={
                'from': previous,
                'to': current,
                'reason': 'user_went_back_to_review_or_edit',
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
        return True
    return False


def clear_home_autofluxo_pause(step: str | None = None) -> None:
    paused = str(st.session_state.get(AUTOFLOW_PAUSE_STEP_KEY) or '').strip().lower()
    if step is None or paused == str(step).strip().lower():
        st.session_state.pop(AUTOFLOW_PAUSE_STEP_KEY, None)


def pause_home_autofluxo_for_manual_review(step: str, *, reason: str = 'manual_mapping_review') -> None:
    """Pausa o auto-next em telas onde uma mudança do usuário deve ficar visível."""
    normalized = str(step or '').strip().lower()
    if not normalized:
        return
    current_lock = st.session_state.get(AUTOFLOW_MANUAL_LOCK_KEY)
    if isinstance(current_lock, dict) and current_lock.get('target_step') == normalized and current_lock.get('reason') == reason:
        return
    st.session_state[AUTOFLOW_PAUSE_STEP_KEY] = normalized
    st.session_state[AUTOFLOW_MANUAL_LOCK_KEY] = {
        'target_step': normalized,
        'reason': reason,
        'responsible_file': RESPONSIBLE_FILE,
    }
    add_audit_event(
        'autofluxo_paused_for_manual_review',
        area='AUTOFLOW',
        step=normalized,
        details={'reason': reason, 'responsible_file': RESPONSIBLE_FILE},
    )


def _move_to_step(next_step: str, *, current: str, operation: str, reason: str) -> None:
    move_signature = f'{current}->{next_step}:{operation}:{reason}'
    previous_signature = str(st.session_state.get(AUTOFLOW_LAST_MOVE_KEY) or '')
    if previous_signature == move_signature:
        return

    st.session_state[WIZARD_STEP_KEY] = next_step
    st.session_state[AUTOFLOW_LAST_STEP_KEY] = next_step
    st.session_state[AUTOFLOW_LAST_MOVE_KEY] = move_signature
    try:
        st.query_params['step'] = next_step
    except Exception:
        pass
    add_audit_event(
        'autofluxo_step_advanced',
        area='AUTOFLOW',
        step=next_step,
        details={
            'from': current,
            'to': next_step,
            'operation': operation,
            'reason': reason,
            'human_click_removed': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    st.rerun()


def _manual_navigation_is_locked() -> bool:
    lock = st.session_state.get(AUTOFLOW_MANUAL_LOCK_KEY)
    if not isinstance(lock, dict):
        return False
    target_step = str(lock.get('target_step') or '').strip().lower()
    current = str(st.session_state.get(WIZARD_STEP_KEY) or '').strip().lower()
    return bool(target_step and (target_step == current or target_step == '__home_choice__'))


def _autoflow_enabled() -> bool:
    # Estabilização urgente: autoavanço agressivo desligado por padrão.
    # Ele causava reruns e saltos de tela em qualquer ação do usuário.
    if AUTOFLOW_ENABLED_KEY not in st.session_state:
        st.session_state[AUTOFLOW_ENABLED_KEY] = False
    return bool(st.session_state.get(AUTOFLOW_ENABLED_KEY, False))


def run_home_autofluxo() -> None:
    """Autoavanço seguro do wizard.

    O auto-next fica desligado por padrão para preservar estabilidade visual.
    Fluxos manuais continuam funcionando sem a tela trocar de lugar após cada
    seleção, digitação ou clique.
    """
    if _manual_navigation_is_locked():
        add_audit_event(
            'autofluxo_blocked_by_manual_navigation',
            area='AUTOFLOW',
            step=st.session_state.get(WIZARD_STEP_KEY),
            details={'lock': st.session_state.get(AUTOFLOW_MANUAL_LOCK_KEY), 'responsible_file': RESPONSIBLE_FILE},
        )
        return

    if not _autoflow_enabled():
        return
    if st.session_state.get(HOME_ACTIVE_OPERATION_KEY) != FLOW_WIZARD_VALUE:
        return
    if not bool(st.session_state.get(HOME_ALLOW_OPERATION_KEY)):
        return

    operation = _sync_operation_from_model()
    current = _current_step()

    if _remember_direction_and_respect_back_navigation(current):
        return

    if current in MANUAL_REVIEW_STEPS:
        pause_home_autofluxo_for_manual_review(current, reason='current_step_requires_human_review')
        return

    paused_step = str(st.session_state.get(AUTOFLOW_PAUSE_STEP_KEY) or '').strip().lower()
    if paused_step == current:
        return

    if current in {STEP_PREVIEW, STEP_DOWNLOAD}:
        return
    if not operation:
        return
    if not _step_ready_for_autonext(current, operation):
        return

    next_step = _next_step_for(current, operation)
    if next_step == current:
        return

    reason = 'safe_prerequisite_already_complete'
    if current == STEP_PRECIFICACAO:
        reason = 'optional_pricing_skipped_when_disabled'
    elif current == STEP_OPERACAO:
        reason = 'operation_already_detected'
    elif current == STEP_MODELO:
        reason = 'bling_model_already_loaded'
    elif current == STEP_ORIGEM:
        reason = 'origin_already_selected'
    elif current == STEP_REGRAS:
        reason = 'rules_already_confirmed'
    elif current == STEP_ENTRADA:
        reason = 'input_context_ready'

    _move_to_step(next_step, current=current, operation=operation, reason=reason)


__all__ = ['run_home_autofluxo', 'clear_home_autofluxo_pause', 'pause_home_autofluxo_for_manual_review']
