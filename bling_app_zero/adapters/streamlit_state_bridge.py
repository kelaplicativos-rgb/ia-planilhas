from __future__ import annotations

from typing import Any

import streamlit as st

from bling_app_zero.core.app_state import AppState
from bling_app_zero.core.navigation_controller import NavigationState

RESPONSIBLE_FILE = 'bling_app_zero/adapters/streamlit_state_bridge.py'


def app_state_from_streamlit() -> AppState:
    return AppState.from_mapping(dict(st.session_state))


def sync_app_state_to_streamlit(state: AppState) -> None:
    current_keys = set(str(key) for key in st.session_state.keys())
    next_values = state.snapshot()
    next_keys = set(str(key) for key in next_values.keys())

    for key in current_keys - next_keys:
        try:
            st.session_state.pop(key, None)
        except Exception:
            pass
    for key, value in next_values.items():
        st.session_state[key] = value


def navigation_state_from_streamlit() -> NavigationState:
    params: dict[str, str] = {}
    try:
        for key, value in dict(st.query_params).items():
            if isinstance(value, list):
                params[str(key)] = str(value[0] if value else '')
            else:
                params[str(key)] = str(value or '')
    except Exception:
        params = {}
    return NavigationState(params)


def sync_navigation_to_streamlit(navigation: NavigationState) -> None:
    target = navigation.snapshot()
    try:
        for key in list(st.query_params.keys()):
            if key not in target:
                st.query_params.pop(key, None)
        for key, value in target.items():
            if value:
                st.query_params[key] = value
            else:
                st.query_params.pop(key, None)
    except Exception:
        pass


def streamlit_state_mapping() -> dict[str, Any]:
    return dict(st.session_state)


__all__ = [
    'app_state_from_streamlit',
    'navigation_state_from_streamlit',
    'streamlit_state_mapping',
    'sync_app_state_to_streamlit',
    'sync_navigation_to_streamlit',
]
