from __future__ import annotations

import importlib
import os
from collections.abc import MutableMapping
from typing import Any

RESPONSIBLE_FILE = 'bling_app_zero/core/ai_runtime_context.py'

SESSION_AI_LIMIT_DEFAULT = 5
SESSION_AI_LIMIT_KEY = 'ai_real_mapping_session_limit'
SESSION_AI_USED_KEY = 'ai_real_mapping_session_used'
_FALLBACK_STATE: dict[str, Any] = {}


def streamlit_module() -> Any | None:
    try:
        return importlib.import_module('streamlit')
    except Exception:
        return None


def state_store(state: MutableMapping[str, Any] | None = None) -> MutableMapping[str, Any]:
    if state is not None:
        return state
    st = streamlit_module()
    if st is not None:
        try:
            return st.session_state
        except Exception:
            pass
    return _FALLBACK_STATE


def secrets_store() -> Any:
    st = streamlit_module()
    if st is not None:
        try:
            return st.secrets
        except Exception:
            return {}
    return {}


def read_secret(path: tuple[str, ...]) -> str:
    try:
        current: Any = secrets_store()
        for part in path:
            if hasattr(current, 'get'):
                current = current.get(part, '')
            else:
                current = current[part]
            if current in (None, ''):
                return ''
        return str(current or '').strip()
    except Exception:
        return ''


def get_secret_value(key: str) -> str:
    key = str(key or '').strip()
    if not key:
        return ''
    env_value = os.getenv(key, '')
    if env_value:
        return str(env_value).strip()
    direct = read_secret((key,))
    if direct:
        return direct
    lower_key = key.lower()
    if lower_key == 'openai_api_key':
        for path in (('openai', 'api_key'), ('openai', 'OPENAI_API_KEY'), ('openai', 'key'), ('openai_api_key',), ('api_key',)):
            value = read_secret(path)
            if value:
                return value
    if lower_key == 'openai_model':
        for path in (('openai', 'model'), ('OPENAI_MODEL',), ('openai_model',)):
            value = read_secret(path)
            if value:
                return value
    return ''


def get_ai_session_limit(*, state: MutableMapping[str, Any] | None = None) -> int:
    configured = read_secret(('openai', 'session_limit')) or read_secret(('OPENAI_SESSION_LIMIT',))
    try:
        limit = int(str(configured or '').strip() or SESSION_AI_LIMIT_DEFAULT)
    except Exception:
        limit = SESSION_AI_LIMIT_DEFAULT
    store = state_store(state)
    try:
        store.setdefault(SESSION_AI_LIMIT_KEY, limit)
        return max(0, int(store.get(SESSION_AI_LIMIT_KEY) or limit))
    except Exception:
        return max(0, int(limit))


def remaining_ai_session_calls(*, state: MutableMapping[str, Any] | None = None) -> int:
    limit = get_ai_session_limit(state=state)
    store = state_store(state)
    try:
        used = int(store.get(SESSION_AI_USED_KEY, 0) or 0)
        return max(0, limit - used)
    except Exception:
        return limit


def consume_ai_session_call(*, state: MutableMapping[str, Any] | None = None) -> bool:
    if remaining_ai_session_calls(state=state) <= 0:
        return False
    store = state_store(state)
    try:
        store[SESSION_AI_USED_KEY] = int(store.get(SESSION_AI_USED_KEY, 0) or 0) + 1
    except Exception:
        pass
    return True


__all__ = [
    'RESPONSIBLE_FILE',
    'SESSION_AI_LIMIT_DEFAULT',
    'SESSION_AI_LIMIT_KEY',
    'SESSION_AI_USED_KEY',
    'consume_ai_session_call',
    'get_ai_session_limit',
    'get_secret_value',
    'read_secret',
    'remaining_ai_session_calls',
    'secrets_store',
    'state_store',
    'streamlit_module',
]
