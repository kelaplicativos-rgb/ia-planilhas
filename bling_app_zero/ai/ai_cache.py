from __future__ import annotations

import hashlib
import json
from typing import Any

import streamlit as st

AI_CACHE_KEY = 'mapeia_ai_cache'


def _stable_json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        return str(value)


def make_cache_key(task: str, payload: dict[str, Any], *, model: str = '') -> str:
    raw = _stable_json({'task': task, 'payload': payload, 'model': model})
    digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()
    return f'{task}:{digest}'


def get_ai_cache() -> dict[str, Any]:
    cache = st.session_state.get(AI_CACHE_KEY)
    if not isinstance(cache, dict):
        cache = {}
        st.session_state[AI_CACHE_KEY] = cache
    return cache


def cache_get(key: str) -> Any | None:
    return get_ai_cache().get(key)


def cache_set(key: str, value: Any) -> None:
    get_ai_cache()[key] = value


def cache_clear() -> None:
    st.session_state[AI_CACHE_KEY] = {}


__all__ = ['AI_CACHE_KEY', 'cache_clear', 'cache_get', 'cache_set', 'get_ai_cache', 'make_cache_key']
