from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import streamlit as st

from bling_app_zero.adapters.streamlit_state_bridge import (
    app_state_from_streamlit,
    navigation_state_from_streamlit,
    sync_app_state_to_streamlit,
    sync_navigation_to_streamlit,
)
from bling_app_zero.core.app_shortcuts import AppShortcut, CONTEXT_API, CONTEXT_AUTO, CONTEXT_CSV
from bling_app_zero.core.workflow_engine import (
    CONTEXT_API as WORKFLOW_CONTEXT_API,
    CONTEXT_UNIVERSAL as WORKFLOW_CONTEXT_UNIVERSAL,
    current_context_is_api,
    current_operation,
    go_home as workflow_go_home,
    set_wizard,
)
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


def _apply_legacy_streamlit_side_effects(*, context: str = '', step: str = '', api_mode: bool = False) -> None:
    request_scroll_top()
    if context:
        set_entry_context(CONTEXT_BLING_API if context == WORKFLOW_CONTEXT_API else CONTEXT_UNIVERSAL)
    if api_mode:
        activate_api_finish_mode()
    else:
        activate_csv_finish_mode()
    if step:
        set_step_without_rerun(step)


def clear_navigation_params() -> None:
    nav = navigation_state_from_streamlit()
    for key in ('operation_v2', 'step', 'flow', 'origem', 'origin', 'operacao', 'operation', 'context'):
        nav.pop(key)
    sync_navigation_to_streamlit(nav)


def go_home() -> ShortcutExecutionResult:
    state = app_state_from_streamlit()
    nav = navigation_state_from_streamlit()
    result = workflow_go_home(state, nav)
    sync_app_state_to_streamlit(result.state)
    sync_navigation_to_streamlit(result.navigation)
    request_scroll_top()
    return ShortcutExecutionResult(result.needs_rerun, result.needs_rerun, result.message)


def current_operation_adapter(default: str = 'cadastro') -> str:
    return current_operation(app_state_from_streamlit(), default)


def current_context_is_api_adapter() -> bool:
    return current_context_is_api(app_state_from_streamlit())


def set_wizard_base(*, context: str, step: str, operation: str | None = None, origin: str | None = None, api_mode: bool = False) -> None:
    state = app_state_from_streamlit()
    nav = navigation_state_from_streamlit()
    workflow_context = WORKFLOW_CONTEXT_API if context == CONTEXT_BLING_API else WORKFLOW_CONTEXT_UNIVERSAL
    result = set_wizard(
        state,
        nav,
        context=workflow_context,
        step=step,
        operation=operation or '',
        origin=origin or '',
        api_mode=api_mode,
    )
    sync_app_state_to_streamlit(result.state)
    sync_navigation_to_streamlit(result.navigation)
    _apply_legacy_streamlit_side_effects(context=workflow_context, step=step, api_mode=api_mode)


def execute_shortcut(shortcut: AppShortcut, *, home_callback: Callable[[], ShortcutExecutionResult] | None = None) -> ShortcutExecutionResult:
    if shortcut.context == 'home':
        if home_callback:
            return home_callback()
        return go_home()

    state = app_state_from_streamlit()
    context = WORKFLOW_CONTEXT_UNIVERSAL
    api_mode = False
    operation = shortcut.operation or current_operation(state)
    origin = shortcut.origin or ''

    if shortcut.context == CONTEXT_API:
        context = WORKFLOW_CONTEXT_API
        api_mode = True
    elif shortcut.context == CONTEXT_CSV:
        context = WORKFLOW_CONTEXT_UNIVERSAL
        api_mode = False
    elif shortcut.context == CONTEXT_AUTO:
        context = WORKFLOW_CONTEXT_API if current_context_is_api(state) else WORKFLOW_CONTEXT_UNIVERSAL
        api_mode = context == WORKFLOW_CONTEXT_API

    nav = navigation_state_from_streamlit()
    result = set_wizard(state, nav, context=context, step=shortcut.step, operation=operation, origin=origin, api_mode=api_mode)
    sync_app_state_to_streamlit(result.state)
    sync_navigation_to_streamlit(result.navigation)
    _apply_legacy_streamlit_side_effects(context=context, step=shortcut.step, api_mode=api_mode)
    return ShortcutExecutionResult(True, result.needs_rerun, f'Atalho executado: {shortcut.title}')


__all__ = [
    'ShortcutExecutionResult',
    'clear_navigation_params',
    'current_context_is_api_adapter',
    'current_operation_adapter',
    'execute_shortcut',
    'go_home',
    'set_wizard_base',
]
