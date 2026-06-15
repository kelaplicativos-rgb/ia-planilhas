from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.wizard_state import WizardState, normalize_step
from bling_app_zero.ui.home_wizard_scroll import set_scroll_target

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard_rerun.py'
WIZARD_STEP_KEY = 'bling_wizard_step'
NEUTRAL_WIZARD_STATE_KEY = 'neutral_wizard_state_v1'
LAST_RERUN_REASON_KEY = 'home_wizard_last_rerun_reason'
LAST_RERUN_TARGET_KEY = 'home_wizard_last_rerun_target'
FORCE_RERUN_REASONS = {
    'origin_selected',
    'wizard_back_clicked',
    'wizard_next_clicked',
}


def _current_api_mode() -> bool:
    # BLINGSCAN: o modo atual da sessão precisa ter prioridade sobre o snapshot neutro antigo.
    # Sem isso, sair de API para CSV poderia manter api_mode=True e normalizar etapas como modelo -> origem.
    finish_mode = str(st.session_state.get('bling_finish_mode') or '').strip()
    if finish_mode:
        return finish_mode == 'api_direct'
    entry_context = str(st.session_state.get('entry_context') or '').strip()
    if entry_context:
        return entry_context == 'api_direct'
    state = st.session_state.get(NEUTRAL_WIZARD_STATE_KEY)
    if isinstance(state, dict):
        return bool(state.get('api_mode')) or str(state.get('context') or '') == 'api_direct'
    return False


def _return_to_home_after_bling_connection() -> None:
    """Conectar ao Bling não equivale a selecionar o fluxo da API."""
    for key in (
        'home_allow_operation_v2_session',
        'home_single_page_flow_active',
        'home_entry_context',
        'home_bling_connected_same_flow_api_send',
        'bling_finish_mode',
        WIZARD_STEP_KEY,
        NEUTRAL_WIZARD_STATE_KEY,
    ):
        st.session_state.pop(key, None)
    st.session_state['home_active_operation_v2'] = 'home'
    try:
        for key in ('operation_v2', 'step', 'flow', 'origem', 'operacao', 'operation'):
            st.query_params.pop(key, None)
    except Exception:
        pass
    add_audit_event(
        'bling_connection_returned_to_home_without_api_selection',
        area='HOME',
        status='OK',
        details={
            'connection_only': True,
            'api_flow_selected': False,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )


def sync_neutral_wizard_step(step: str) -> None:
    """Mantém o estado neutro do Wizard sincronizado com os caminhos legados."""
    current = st.session_state.get(NEUTRAL_WIZARD_STATE_KEY)
    values = dict(current) if isinstance(current, dict) else {}
    values.update(dict(st.session_state))
    values['step'] = step
    values['api_mode'] = _current_api_mode()
    values['context'] = 'api_direct' if values['api_mode'] else str(values.get('entry_context') or values.get('context') or 'csv_download')
    wizard = WizardState.from_mapping(values)
    st.session_state[NEUTRAL_WIZARD_STATE_KEY] = wizard.to_dict()


def set_step_without_rerun(step: str) -> bool:
    """Atualiza a etapa do wizard somente quando houver mudança real e espelha no Wizard neutro."""
    normalized = normalize_step(step, api_mode=_current_api_mode())
    if not normalized:
        return False
    previous = str(st.session_state.get(WIZARD_STEP_KEY) or '').strip().lower()
    sync_neutral_wizard_step(normalized)
    if previous == normalized:
        return False
    st.session_state[WIZARD_STEP_KEY] = normalized
    set_scroll_target(normalized)
    try:
        st.query_params['step'] = normalized
    except Exception:
        pass
    return True


def safe_rerun(reason: str, *, target_step: str = '') -> None:
    """Executa rerun só quando necessário e deixa trilha de auditoria."""
    normalized_reason = str(reason or 'wizard_state_changed').strip() or 'wizard_state_changed'
    if normalized_reason == 'home_bling_verify_connected':
        _return_to_home_after_bling_connection()
        st.session_state[LAST_RERUN_REASON_KEY] = normalized_reason
        st.session_state[LAST_RERUN_TARGET_KEY] = 'home'
        st.rerun()
        return
    if normalized_reason == 'wizard_reset':
        from bling_app_zero.ui.master_reset import master_reset_to_home

        master_reset_to_home()
        st.session_state[LAST_RERUN_REASON_KEY] = normalized_reason
        st.session_state[LAST_RERUN_TARGET_KEY] = 'home'
        st.rerun()
        return

    normalized_target = normalize_step(target_step or st.session_state.get(WIZARD_STEP_KEY) or '', api_mode=_current_api_mode())

    if target_step:
        changed = set_step_without_rerun(target_step)
    else:
        changed = True
        if normalized_target:
            sync_neutral_wizard_step(normalized_target)

    last_reason = str(st.session_state.get(LAST_RERUN_REASON_KEY) or '')
    last_target = str(st.session_state.get(LAST_RERUN_TARGET_KEY) or '')
    force_rerun = normalized_reason in FORCE_RERUN_REASONS
    if not force_rerun and not changed and last_reason == normalized_reason and last_target == normalized_target:
        return

    if normalized_target:
        set_scroll_target(normalized_target)
    st.session_state[LAST_RERUN_REASON_KEY] = normalized_reason
    st.session_state[LAST_RERUN_TARGET_KEY] = normalized_target
    add_audit_event(
        'wizard_safe_rerun_requested',
        area='WIZARD',
        step=normalized_target,
        status='OK',
        details={
            'reason': normalized_reason,
            'changed_step': changed,
            'forced_rerun': force_rerun,
            'neutral_wizard_synced': True,
            'api_mode_current_priority': True,
            'scroll_target_marked': bool(normalized_target),
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    st.rerun()


__all__ = [
    'FORCE_RERUN_REASONS',
    'safe_rerun',
    'set_step_without_rerun',
    'sync_neutral_wizard_step',
]
