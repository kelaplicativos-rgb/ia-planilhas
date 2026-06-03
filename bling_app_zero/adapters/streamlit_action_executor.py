from __future__ import annotations

import time
from collections.abc import Callable, MutableMapping
from dataclasses import dataclass
from typing import Any

import streamlit as st

from bling_app_zero.core.app_actions import (
    ACTION_CLEAR,
    ACTION_DIAGNOSTIC,
    ACTION_REFRESH,
    ACTION_SHORTCUTS,
    SAFE_CLEAR_KEYS,
    SAFE_CLEAR_PREFIXES,
    TECHNICAL_KEEP_PREFIXES,
    is_known_action,
)

RESPONSIBLE_FILE = 'bling_app_zero/adapters/streamlit_action_executor.py'

FLOW_MENU_KEY = 'bottom_nav_fluxos_open'
LOG_MENU_KEY = 'bottom_nav_logs_open'


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
    session = state if state is not None else st.session_state
    for key in SAFE_CLEAR_KEYS:
        session.pop(key, None)
    for key in list(session.keys()):
        if str(key).startswith(SAFE_CLEAR_PREFIXES):
            session.pop(key, None)
    clear_streamlit_cache()
    session['bottom_nav_last_safe_clear_at'] = time.time()


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
    action_key = str(action or '').strip()
    if not action_key or not is_known_action(action_key):
        return ActionExecutionResult(False, False, 'Ação ignorada ou desconhecida.')

    if action_key == ACTION_REFRESH:
        st.session_state['bottom_nav_last_refresh_at'] = time.time()
        return ActionExecutionResult(True, True, 'Tela atualizada.')

    if action_key == ACTION_CLEAR:
        safe_clear_stuck_state(st.session_state)
        return ActionExecutionResult(True, True, 'Travamentos e caches seguros foram limpos.')

    if action_key == ACTION_SHORTCUTS:
        st.session_state[FLOW_MENU_KEY] = not bool(st.session_state.get(FLOW_MENU_KEY))
        st.session_state[LOG_MENU_KEY] = False
        return ActionExecutionResult(True, False, 'Atalhos alternados.')

    if action_key == ACTION_DIAGNOSTIC:
        st.session_state[LOG_MENU_KEY] = not bool(st.session_state.get(LOG_MENU_KEY))
        st.session_state[FLOW_MENU_KEY] = False
        return ActionExecutionResult(True, False, 'Diagnóstico alternado.')

    return ActionExecutionResult(False, False, 'Ação não executada.')


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
