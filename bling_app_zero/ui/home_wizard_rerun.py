from __future__ import annotations

import streamlit as st

from bling_app_zero.core.audit import add_audit_event

RESPONSIBLE_FILE = 'bling_app_zero/ui/home_wizard_rerun.py'
WIZARD_STEP_KEY = 'bling_wizard_step'
LAST_RERUN_REASON_KEY = 'home_wizard_last_rerun_reason'
LAST_RERUN_TARGET_KEY = 'home_wizard_last_rerun_target'


def set_step_without_rerun(step: str) -> bool:
    """Atualiza a etapa do wizard somente quando houver mudança real."""
    normalized = str(step or '').strip().lower()
    if not normalized:
        return False
    previous = str(st.session_state.get(WIZARD_STEP_KEY) or '').strip().lower()
    if previous == normalized:
        return False
    st.session_state[WIZARD_STEP_KEY] = normalized
    try:
        st.query_params['step'] = normalized
    except Exception:
        pass
    return True


def safe_rerun(reason: str, *, target_step: str = '') -> None:
    """Executa rerun só quando necessário e deixa trilha de auditoria."""
    normalized_target = str(target_step or st.session_state.get(WIZARD_STEP_KEY) or '').strip().lower()
    normalized_reason = str(reason or 'wizard_state_changed').strip() or 'wizard_state_changed'

    if target_step:
        changed = set_step_without_rerun(target_step)
    else:
        changed = True

    last_reason = str(st.session_state.get(LAST_RERUN_REASON_KEY) or '')
    last_target = str(st.session_state.get(LAST_RERUN_TARGET_KEY) or '')
    if not changed and last_reason == normalized_reason and last_target == normalized_target:
        return

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
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    st.rerun()


__all__ = ['set_step_without_rerun', 'safe_rerun']
