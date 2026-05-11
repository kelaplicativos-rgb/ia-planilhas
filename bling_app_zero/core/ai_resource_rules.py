from __future__ import annotations

from typing import Any

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

AI_RESOURCES_SESSION_KEY = 'bling_ai_resource_rules'
AI_RESOURCE_SUGGEST_NCM = 'ai_suggest_ncm'
AI_RESOURCE_IMPROVE_CATALOG_TEXT = 'ai_improve_catalog_text'
AI_RESOURCE_LIMIT_TITLE_60 = 'ai_limit_title_60'
AI_RESOURCE_DESCRIPTION_SIZE = 'ai_description_size'

DESCRIPTION_SIZE_OPTIONS = ('pequena', 'media', 'grande')
DEFAULT_DESCRIPTION_SIZE = 'media'

DEFAULT_AI_RESOURCES: dict[str, Any] = {
    AI_RESOURCE_SUGGEST_NCM: False,
    AI_RESOURCE_IMPROVE_CATALOG_TEXT: False,
    AI_RESOURCE_LIMIT_TITLE_60: True,
    AI_RESOURCE_DESCRIPTION_SIZE: DEFAULT_DESCRIPTION_SIZE,
}


def _safe_description_size(value: Any) -> str:
    text = str(value or '').strip().lower()
    if text in {'média', 'medio', 'médio'}:
        text = 'media'
    if text not in DESCRIPTION_SIZE_OPTIONS:
        return DEFAULT_DESCRIPTION_SIZE
    return text


def normalize_ai_resources(raw: Any) -> dict[str, Any]:
    resources = dict(DEFAULT_AI_RESOURCES)
    if isinstance(raw, dict):
        resources[AI_RESOURCE_SUGGEST_NCM] = bool(raw.get(AI_RESOURCE_SUGGEST_NCM, resources[AI_RESOURCE_SUGGEST_NCM]))
        resources[AI_RESOURCE_IMPROVE_CATALOG_TEXT] = bool(raw.get(AI_RESOURCE_IMPROVE_CATALOG_TEXT, resources[AI_RESOURCE_IMPROVE_CATALOG_TEXT]))
        resources[AI_RESOURCE_LIMIT_TITLE_60] = bool(raw.get(AI_RESOURCE_LIMIT_TITLE_60, resources[AI_RESOURCE_LIMIT_TITLE_60]))
        resources[AI_RESOURCE_DESCRIPTION_SIZE] = _safe_description_size(raw.get(AI_RESOURCE_DESCRIPTION_SIZE, resources[AI_RESOURCE_DESCRIPTION_SIZE]))
    return resources


def get_ai_resources() -> dict[str, Any]:
    if st is None:
        return dict(DEFAULT_AI_RESOURCES)
    current = st.session_state.get(AI_RESOURCES_SESSION_KEY)
    resources = normalize_ai_resources(current)
    st.session_state[AI_RESOURCES_SESSION_KEY] = resources
    return resources


def set_ai_resources(resources: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_ai_resources(resources)
    if st is not None:
        st.session_state[AI_RESOURCES_SESSION_KEY] = normalized
    return normalized


def ai_resource_enabled(key: str, default: bool = False) -> bool:
    resources = get_ai_resources()
    return bool(resources.get(key, default))


def ai_description_size() -> str:
    resources = get_ai_resources()
    return _safe_description_size(resources.get(AI_RESOURCE_DESCRIPTION_SIZE))
