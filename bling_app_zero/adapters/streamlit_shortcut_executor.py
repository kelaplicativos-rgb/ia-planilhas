from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import streamlit as st

from bling_app_zero.core.app_shortcuts import AppShortcut, CONTEXT_API, CONTEXT_AUTO, CONTEXT_CSV
from bling_app_zero.ui.flow_context import CONTEXT_BLING_API, CONTEXT_UNIVERSAL, activate_api_finish_mode, activate_csv_finish_mode, set_entry_context
from bling_app_zero.ui.home_wizard_rerun import set_step_without_rerun
from bling_app_zero.ui.scroll_position import request_scroll_top

RESPONSIBLE_FILE = 'bling_app_zero/adapters/streamlit_shortcut_executor.py'

ACTIVE_FLOW_KEY = 'home_active_operation_v2'
HOME_ALLOW_FLOW_KEY = 'home_allow_operation_v2_session'
FLOW_HOME = 'home'
FLOW_WIZARD = 'wizard_cadastro_estoque'


@dataclass(frozen=True)
class ShortcutExecutionResult:
    handled: bool
    needs_rerun: bool = True
    message: str = ''


def clear_navigation_params() -> None:
    try:
        for key in ('operation_v2', 'step', 'flow', 'origem', 'operacao', 'operation'):
            st.query_params.pop(key, None)
    except Exception:
        pass


def go_home() -> ShortcutExecutionResult:
    request_scroll_top()
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_HOME
    st.session_state[HOME_ALLOW_FLOW_KEY] = False
    st.session_state['home_single_page_flow_active'] = False
    clear_navigation_params()
    return ShortcutExecutionResult(True, True, 'Voltando para o início.')


def current_operation(default: str = 'cadastro') -> str:
    return str(st.session_state.get('direct_bling_operation_choice') or st.session_state.get('home_slim_flow_operation') or default)


def current_context_is_api() -> bool:
    return str(st.session_state.get('bling_finish_mode') or '') == 'api_direct'


def set_wizard_base(*, context: str, step: str, operation: str | None = None, origin: str | None = None, api_mode: bool = False) -> None:
    request_scroll_top()
    st.session_state[ACTIVE_FLOW_KEY] = FLOW_WIZARD
    st.session_state[HOME_ALLOW_FLOW_KEY] = True
    st.session_state['home_single_page_flow_active'] = True
    set_entry_context(context)
    if api_mode:
        activate_api_finish_mode()
    else:
        activate_csv_finish_mode()
    if operation:
        st.session_state['direct_bling_operation_choice'] = operation
        st.session_state['home_slim_flow_operation'] = operation
        st.session_state['home_detected_operation'] = operation
        st.session_state['operacao_final'] = operation
        st.session_state['tipo_operacao_final'] = operation
        st.session_state['model_contract_type'] = operation
    if origin:
        st.session_state['home_slim_flow_origin'] = origin
        st.session_state['origem_final'] = origin
    set_step_without_rerun(step)
    try:
        st.query_params['operation_v2'] = FLOW_WIZARD
        st.query_params['step'] = step
        if operation:
            st.query_params['operation'] = operation
    except Exception:
        pass


def execute_shortcut(shortcut: AppShortcut, *, home_callback: Callable[[], None] | None = None) -> ShortcutExecutionResult:
    if shortcut.context == 'home':
        if home_callback:
            home_callback()
            return ShortcutExecutionResult(True, True, 'Voltando para o início.')
        return go_home()

    context = CONTEXT_UNIVERSAL
    api_mode = False
    operation = shortcut.operation or current_operation()
    origin = shortcut.origin or None

    if shortcut.context == CONTEXT_API:
        context = CONTEXT_BLING_API
        api_mode = True
    elif shortcut.context == CONTEXT_CSV:
        context = CONTEXT_UNIVERSAL
        api_mode = False
    elif shortcut.context == CONTEXT_AUTO:
        context = CONTEXT_BLING_API if current_context_is_api() else CONTEXT_UNIVERSAL
        api_mode = context == CONTEXT_BLING_API

    set_wizard_base(context=context, step=shortcut.step, operation=operation, origin=origin, api_mode=api_mode)
    return ShortcutExecutionResult(True, True, f'Atalho executado: {shortcut.title}')


__all__ = [
    'ShortcutExecutionResult',
    'clear_navigation_params',
    'current_context_is_api',
    'current_operation',
    'execute_shortcut',
    'go_home',
    'set_wizard_base',
]
