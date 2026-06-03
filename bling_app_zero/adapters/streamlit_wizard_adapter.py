from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

from bling_app_zero.core.wizard_engine import WizardCommandResult, go_to_step, mark_step_ready, next_step, previous_step, set_operation, set_origin
from bling_app_zero.core.wizard_state import WizardState
from bling_app_zero.ui.home_wizard_rerun import set_step_without_rerun
from bling_app_zero.ui.scroll_position import request_scroll_top

RESPONSIBLE_FILE = 'bling_app_zero/adapters/streamlit_wizard_adapter.py'
WIZARD_STATE_KEY = 'neutral_wizard_state_v1'


@dataclass(frozen=True)
class StreamlitWizardResult:
    handled: bool
    needs_rerun: bool = True
    message: str = ''
    warning: str = ''


def wizard_from_streamlit() -> WizardState:
    stored = st.session_state.get(WIZARD_STATE_KEY)
    if isinstance(stored, dict):
        merged: dict[str, Any] = dict(stored)
        merged.update(dict(st.session_state))
        return WizardState.from_mapping(merged)
    return WizardState.from_mapping(dict(st.session_state))


def sync_wizard_to_streamlit(wizard: WizardState) -> None:
    data = wizard.to_dict()
    st.session_state[WIZARD_STATE_KEY] = data
    st.session_state['bling_wizard_step'] = wizard.step
    st.session_state['direct_bling_operation_choice'] = wizard.operation
    st.session_state['home_slim_flow_operation'] = wizard.operation
    st.session_state['operacao_final'] = wizard.operation
    st.session_state['tipo_operacao_final'] = wizard.operation
    st.session_state['model_contract_type'] = wizard.operation
    if wizard.origin:
        st.session_state['home_slim_flow_origin'] = wizard.origin
        st.session_state['origem_final'] = wizard.origin
    st.session_state['bling_finish_mode'] = 'api_direct' if wizard.api_mode else 'csv_download'
    try:
        st.query_params['step'] = wizard.step
        st.query_params['operation'] = wizard.operation
        if wizard.origin:
            st.query_params['origin'] = wizard.origin
    except Exception:
        pass
    set_step_without_rerun(wizard.step)


def _apply_result(result: WizardCommandResult) -> StreamlitWizardResult:
    if result.allowed:
        sync_wizard_to_streamlit(result.wizard)
        request_scroll_top()
    return StreamlitWizardResult(result.allowed, result.needs_rerun, result.message, result.warning)


def wizard_go_to(step: str, *, force: bool = False) -> StreamlitWizardResult:
    return _apply_result(go_to_step(wizard_from_streamlit(), step, force=force))


def wizard_next(*, force: bool = False) -> StreamlitWizardResult:
    return _apply_result(next_step(wizard_from_streamlit(), force=force))


def wizard_previous() -> StreamlitWizardResult:
    return _apply_result(previous_step(wizard_from_streamlit()))


def wizard_mark_ready(step: str | None = None) -> WizardState:
    wizard = mark_step_ready(wizard_from_streamlit(), step)
    sync_wizard_to_streamlit(wizard)
    return wizard


def wizard_set_origin(origin: str) -> StreamlitWizardResult:
    return _apply_result(set_origin(wizard_from_streamlit(), origin))


def wizard_set_operation(operation: str) -> StreamlitWizardResult:
    return _apply_result(set_operation(wizard_from_streamlit(), operation))


__all__ = [
    'StreamlitWizardResult',
    'WIZARD_STATE_KEY',
    'sync_wizard_to_streamlit',
    'wizard_from_streamlit',
    'wizard_go_to',
    'wizard_mark_ready',
    'wizard_next',
    'wizard_previous',
    'wizard_set_operation',
    'wizard_set_origin',
]
