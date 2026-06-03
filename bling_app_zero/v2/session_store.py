from __future__ import annotations

import importlib
from collections.abc import MutableMapping
from typing import Any

from bling_app_zero.v2.user_context import get_user_context, scoped_key

_FALLBACK_STATE: dict[str, Any] = {}


def _streamlit_module() -> Any | None:
    try:
        return importlib.import_module('streamlit')
    except Exception:
        return None


def state_store() -> MutableMapping[str, Any]:
    st = _streamlit_module()
    if st is not None:
        try:
            return st.session_state
        except Exception:
            pass
    return _FALLBACK_STATE


def state_key(name: str) -> str:
    return scoped_key(name)


def get_state(name: str, default: Any = None) -> Any:
    return state_store().get(state_key(name), default)


def set_state(name: str, value: Any) -> None:
    state_store()[state_key(name)] = value


def pop_state(name: str, default: Any = None) -> Any:
    return state_store().pop(state_key(name), default)


def has_state(name: str) -> bool:
    return state_key(name) in state_store()


def clear_namespace(prefix: str = '') -> int:
    store = state_store()
    context = get_user_context()
    namespace_prefix = f'v2:{context.namespace}:'
    wanted_prefix = namespace_prefix + str(prefix or '')
    keys = [key for key in list(store.keys()) if str(key).startswith(wanted_prefix)]
    for key in keys:
        store.pop(key, None)
    return len(keys)


def widget_key(name: str) -> str:
    return state_key(f'widget:{name}')


__all__ = ['clear_namespace', 'get_state', 'has_state', 'pop_state', 'set_state', 'state_key', 'state_store', 'widget_key']
