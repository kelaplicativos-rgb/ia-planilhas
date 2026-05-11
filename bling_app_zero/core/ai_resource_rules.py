from __future__ import annotations

from typing import Any

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

AI_RESOURCES_SESSION_KEY = 'bling_ai_resource_rules'
AI_RESOURCE_SUGGEST_NCM = 'ai_suggest_ncm'
AI_RESOURCE_IMPROVE_CATALOG_TEXT = 'ai_improve_catalog_text'

DEFAULT_AI_RESOURCES: dict[str, bool] = {
    AI_RESOURCE_SUGGEST_NCM: False,
    AI_RESOURCE_IMPROVE_CATALOG_TEXT: False,
}


def normalize_ai_resources(raw: Any) -> dict[str, bool]:
    resources = dict(DEFAULT_AI_RESOURCES)
    if isinstance(raw, dict):
        for key in resources:
            resources[key] = bool(raw.get(key, resources[key]))
    return resources


def get_ai_resources() -> dict[str, bool]:
    if st is None:
        return dict(DEFAULT_AI_RESOURCES)
    current = st.session_state.get(AI_RESOURCES_SESSION_KEY)
    resources = normalize_ai_resources(current)
    st.session_state[AI_RESOURCES_SESSION_KEY] = resources
    return resources


def set_ai_resources(resources: dict[str, Any]) -> dict[str, bool]:
    normalized = normalize_ai_resources(resources)
    if st is not None:
        st.session_state[AI_RESOURCES_SESSION_KEY] = normalized
    return normalized


def ai_resource_enabled(key: str, default: bool = False) -> bool:
    resources = get_ai_resources()
    return bool(resources.get(key, default))
