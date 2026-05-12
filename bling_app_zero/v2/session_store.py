from __future__ import annotations

from typing import Any

import streamlit as st

from bling_app_zero.v2.user_context import get_user_context, scoped_key


def state_key(name: str) -> str:
    return scoped_key(name)


def get_state(name: str, default: Any = None) -> Any:
    return st.session_state.get(state_key(name), default)


def set_state(name: str, value: Any) -> None:
    st.session_state[state_key(name)] = value


def pop_state(name: str, default: Any = None) -> Any:
    return st.session_state.pop(state_key(name), default)


def has_state(name: str) -> bool:
    return state_key(name) in st.session_state


def clear_namespace(prefix: str = '') -> int:
    context = get_user_context()
    namespace_prefix = f'v2:{context.namespace}:'
    wanted_prefix = namespace_prefix + str(prefix or '')
    keys = [key for key in list(st.session_state.keys()) if str(key).startswith(wanted_prefix)]
    for key in keys:
        st.session_state.pop(key, None)
    return len(keys)


def widget_key(name: str) -> str:
    return state_key(f'widget:{name}')


__all__ = ['clear_namespace', 'get_state', 'has_state', 'pop_state', 'set_state', 'state_key', 'widget_key']
