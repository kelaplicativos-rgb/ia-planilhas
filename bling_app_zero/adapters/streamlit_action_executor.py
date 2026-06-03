from __future__ import annotations

from collections.abc import Callable, MutableMapping
from dataclasses import dataclass
from typing import Any

import streamlit as st

from bling_app_zero.adapters.streamlit_state_bridge import app_state_from_streamlit, sync_app_state_to_streamlit
from bling_app_zero.core.app_action_engine import FLOW_MENU_KEY, LOG_MENU_KEY, execute_action_on_state
from bling_app_zero.core.app_actions import TECHNICAL_KEEP_PREFIXES

RESPONSIBLE_FILE = 'bling_app_zero/adapters/streamlit_action_executor.py'


@dataclass(frozen=True)
class ActionExecutionResult:
    handled: bool
    needs_rerun: bool = False
    message: str = ''


def clear_streamlit_cache() -> None:
    try:
        st.cache_data.clear()
    except Exception:
        pass
    try:
        st.cache_resource.clear()
    except Exception:
        pass


def safe_clear_stuck_state(state: MutableMapping[str, Any] | None = None) -> None:
    app_state = app_state_from_streamlit()
    result = execute_action_on_state(app_state, 'clear')
    sync_app_state_to_streamlit(app_state)
    if result.clear_cache:
        clear_streamlit_cache()


def preserve_technical_state(state: MutableMapping[str, Any] | None = None) -> dict[str, Any]:
    session = state if state is not None else st.session_state
    kept: dict[str, Any] = {}
    for key, value in list(session.items()):
        if any(str(key).startswith(prefix) for prefix in TECHNICAL_KEEP_PREFIXES):
            kept[str(key)] = value
    return kept


def hard_reset_session(*, after_reset: Callable[[], None] | None = None) -> None:
    kept = preserve_technical_state(st.session_state)
    st.session_state.clear()
    for key, value in kept.items():
        st.session_state[key] = value
    clear_streamlit_cache()
    if after_reset:
        after_reset()


def execute_app_action(action: object) -> ActionExecutionResult:
    app_state = app_state_from_streamlit()
    result = execute_action_on_state(app_state, action)
    sync_app_state_to_streamlit(app_state)
    if result.clear_cache:
        clear_streamlit_cache()
    return ActionExecutionResult(result.handled, result.needs_rerun, result.message)


__all__ = [
    'ActionExecutionResult',
    'FLOW_MENU_KEY',
    'LOG_MENU_KEY',
    'clear_streamlit_cache',
    'execute_app_action',
    'hard_reset_session',
    'preserve_technical_state',
    'safe_clear_stuck_state',
]
