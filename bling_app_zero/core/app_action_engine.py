from __future__ import annotations

import time
from dataclasses import dataclass

from bling_app_zero.core.app_actions import (
    ACTION_CLEAR,
    ACTION_DIAGNOSTIC,
    ACTION_REFRESH,
    ACTION_SHORTCUTS,
    SAFE_CLEAR_KEYS,
    SAFE_CLEAR_PREFIXES,
    is_known_action,
)
from bling_app_zero.core.app_state import AppState, clear_by_keys_and_prefixes

RESPONSIBLE_FILE = 'bling_app_zero/core/app_action_engine.py'

FLOW_MENU_KEY = 'bottom_nav_fluxos_open'
LOG_MENU_KEY = 'bottom_nav_logs_open'


@dataclass(frozen=True)
class AppActionResult:
    handled: bool
    needs_rerun: bool = False
    clear_cache: bool = False
    message: str = ''


def clear_stuck_state(state: AppState) -> AppState:
    clear_by_keys_and_prefixes(state, keys=SAFE_CLEAR_KEYS, prefixes=SAFE_CLEAR_PREFIXES)
    state.set('bottom_nav_last_safe_clear_at', time.time())
    return state


def execute_action_on_state(state: AppState, action: object) -> AppActionResult:
    action_key = str(action or '').strip()
    if not action_key or not is_known_action(action_key):
        return AppActionResult(False, False, False, 'Ação ignorada ou desconhecida.')

    if action_key == ACTION_REFRESH:
        state.set('bottom_nav_last_refresh_at', time.time())
        return AppActionResult(True, True, False, 'Tela atualizada.')

    if action_key == ACTION_CLEAR:
        clear_stuck_state(state)
        return AppActionResult(True, True, True, 'Travamentos e caches seguros foram limpos.')

    if action_key == ACTION_SHORTCUTS:
        state.set(FLOW_MENU_KEY, not bool(state.get(FLOW_MENU_KEY)))
        state.set(LOG_MENU_KEY, False)
        return AppActionResult(True, False, False, 'Atalhos alternados.')

    if action_key == ACTION_DIAGNOSTIC:
        state.set(LOG_MENU_KEY, not bool(state.get(LOG_MENU_KEY)))
        state.set(FLOW_MENU_KEY, False)
        return AppActionResult(True, False, False, 'Diagnóstico alternado.')

    return AppActionResult(False, False, False, 'Ação não executada.')


__all__ = [
    'AppActionResult',
    'FLOW_MENU_KEY',
    'LOG_MENU_KEY',
    'clear_stuck_state',
    'execute_action_on_state',
]
