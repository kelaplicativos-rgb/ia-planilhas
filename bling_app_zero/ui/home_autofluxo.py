from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.features_runtime.router import active_contract, active_steps as runtime_active_steps, feature_needs_pricing
from bling_app_zero.ui.cadastro_wizard_state import cadastro_context_ready
from bling_app_zero.ui.home_wizard_constants import (
    CADASTRO_STEPS,
    FLOW_OPERATION_KEY,
    FLOW_ORIGIN_KEY,
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
    UNIVERSAL_OPERATION_VALUE,
    UNIVERSAL_STEPS,
    WIZARD_STEP_KEY,
)
from bling_app_zero.ui.home_wizard_rerun import safe_rerun, set_step_without_rerun
from bling_app_zero.ui.home_wizard_state import has_home_models
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


def _sync_operation_from_runtime() -> str:
    """Mantém o autoavanço no contrato ativo do runtime.

    Antes este arquivo forçava UNIVERSAL em qualquer modelo carregado. Agora ele
    respeita cadastro/estoque/preço/API/CSV declarados no features_runtime.
    """
    contract = active_contract()
    operation = contract.operation or UNIVERSAL_OPERATION_VALUE
    current = str(st.session_state.get(FLOW_OPERATION_KEY) or '').strip().lower()
    if current != operation:
        st.session_state[FLOW_OPERATION_KEY] = operation
        st.session_state['operacao_final'] = operation
        st.session_state['tipo_operacao_final'] = operation
        st.session_state['home_detected_operation'] = operation
        st.session_state['home_slim_flow_operation'] = operation
        add_audit_event(
            'autofluxo_operation_synced_runtime',
            area='AUTOFLOW',
            step=st.session_state.get(WIZARD_STEP_KEY),
            details={
                'operation': operation,
                'feature_contract': contract.key,
                'mode': contract.mode,
                'reason': 'runtime_feature_contract',
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
    return operation


def _active_steps() -> list[str]:
    steps = [step for step in runtime_active_steps() if step]
    return steps or list(UNIVERSAL_STEPS or CADASTRO_STEPS)


def _current_step() -> str:
    steps = _active_steps()
    current = str(st.session_state.get(WIZARD_STEP_KEY) or (steps[0] if steps else STEP_MODELO)).strip().lower()
    if current not in steps:
        current = steps[0] if steps else STEP_MODELO
    set_step_without_rerun(current)
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
    if not feature_needs_pricing():
        return False
    if bool(st.session_state.get('home_precificacao_inicial')):
        return True
    if bool(st.session_state.get('home_pricing_enabled_toggle')):
        return True
    config = st.session_state.get('home_pricing_config')
    return isinstance(config, dict) and bool(config)


def _step_ready_for_autonext(step: str, operation: str) -> bool:
    _ = operation
    if step == STEP_MODELO:
        return has_home_models()
    if step == STEP_OPERACAO:
        return True
    if step == STEP_PRECIFICACAO:
        return not _pricing_is_active()
    if step == STEP_ORIGEM:
        return _current_origin() in {'arquivo', 'site'}
    if step == STEP_ENTRADA:
        return cadastro_context_ready()
    if step in MANUAL_REVIEW_STEPS:
        return False
    if step == STEP_REGRAS:
        return rules_center_ready()
    return False


def _next_step_for(step: str, operation: str) -> str:
    _ = operation
    steps = _active_steps()
    if step in {STEP_PREVIEW, STEP_DOWNLOAD}:
        return step
    if step not in steps:
        return steps[0] if steps else STEP_MODELO
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

    set_step_without_rerun(next_step)
    st.session_state[AUTOFLOW_LAST_STEP_KEY] = next_step
    st.session_state[AUTOFLOW_LAST_MOVE_KEY] = move_signature
    add_audit_event(
        'autofluxo_step_advanced',
        area='AUTOFLOW',
        step=next_step,
        details={
            'from': current,
            'to': next_step,
            'operation': operation,
            'feature_contract': active_contract().key,
            'reason': reason,
            'human_click_removed': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    safe_rerun('autofluxo_step_advanced', target_step=next_step)


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
    Quando for reativado, opera no contrato ativo do runtime e não força universal.
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

    operation = _sync_operation_from_runtime()
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
        reason = 'operation_legacy_step_skipped'
    elif current == STEP_MODELO:
        reason = 'destination_model_already_loaded'
    elif current == STEP_ORIGEM:
        reason = 'origin_already_selected'
    elif current == STEP_REGRAS:
        reason = 'rules_already_confirmed'
    elif current == STEP_ENTRADA:
        reason = 'input_context_ready'

    _move_to_step(next_step, current=current, operation=operation, reason=reason)


__all__ = ['run_home_autofluxo', 'clear_home_autofluxo_pause', 'pause_home_autofluxo_for_manual_review']
