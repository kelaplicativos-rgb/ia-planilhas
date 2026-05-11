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
AI_RESOURCE_ORTHOGRAPHY_GRAMMAR = 'ai_orthography_grammar'
AI_RESOURCE_MARKETPLACE_TEXT_GUARD = 'ai_marketplace_text_guard'
AI_RESOURCE_OUT_OF_CONTEXT_FILTER = 'ai_out_of_context_filter'
AI_RESOURCE_BLOCKED_TERMS = 'ai_marketplace_blocked_terms'
AI_RESOURCE_CONTEXT_FILTER_TERMS = 'ai_context_filter_terms'

DESCRIPTION_SIZE_OPTIONS = ('pequena', 'media', 'grande')
DEFAULT_DESCRIPTION_SIZE = 'media'

DEFAULT_BLOCKED_TERMS_TEXT = '\n'.join([
    'réplica',
    'primeira linha',
    'garantia vitalícia',
    '100% garantido',
    'melhor do mercado',
    'produto original',
])

DEFAULT_CONTEXT_FILTER_TERMS_TEXT = '\n'.join([
    'aqui você coloca a descrição',
    'descrição do produto aqui',
    'coloque aqui',
    'insira aqui',
    'texto exemplo',
    'lorem ipsum',
])

DEFAULT_AI_RESOURCES: dict[str, Any] = {
    AI_RESOURCE_SUGGEST_NCM: False,
    AI_RESOURCE_IMPROVE_CATALOG_TEXT: False,
    AI_RESOURCE_LIMIT_TITLE_60: True,
    AI_RESOURCE_DESCRIPTION_SIZE: DEFAULT_DESCRIPTION_SIZE,
    AI_RESOURCE_ORTHOGRAPHY_GRAMMAR: False,
    AI_RESOURCE_MARKETPLACE_TEXT_GUARD: False,
    AI_RESOURCE_OUT_OF_CONTEXT_FILTER: False,
    AI_RESOURCE_BLOCKED_TERMS: DEFAULT_BLOCKED_TERMS_TEXT,
    AI_RESOURCE_CONTEXT_FILTER_TERMS: DEFAULT_CONTEXT_FILTER_TERMS_TEXT,
}


def _safe_description_size(value: Any) -> str:
    text = str(value or '').strip().lower()
    if text in {'média', 'medio', 'médio'}:
        text = 'media'
    if text not in DESCRIPTION_SIZE_OPTIONS:
        return DEFAULT_DESCRIPTION_SIZE
    return text


def _safe_multiline_text(value: Any, fallback: str = '') -> str:
    text = str(value if value is not None else '').replace('\r\n', '\n').replace('\r', '\n')
    lines = []
    seen = set()
    for line in text.split('\n'):
        clean = ' '.join(str(line or '').strip().split())
        key = clean.lower()
        if clean and key not in seen:
            lines.append(clean)
            seen.add(key)
    if not lines and fallback:
        return fallback
    return '\n'.join(lines[:120])


def _terms_from_text(text: Any) -> list[str]:
    normalized = _safe_multiline_text(text)
    if not normalized:
        return []
    terms: list[str] = []
    for line in normalized.split('\n'):
        clean = line.strip()
        if clean:
            terms.append(clean)
    return terms


def normalize_ai_resources(raw: Any) -> dict[str, Any]:
    resources = dict(DEFAULT_AI_RESOURCES)
    if isinstance(raw, dict):
        resources[AI_RESOURCE_SUGGEST_NCM] = bool(raw.get(AI_RESOURCE_SUGGEST_NCM, resources[AI_RESOURCE_SUGGEST_NCM]))
        resources[AI_RESOURCE_IMPROVE_CATALOG_TEXT] = bool(raw.get(AI_RESOURCE_IMPROVE_CATALOG_TEXT, resources[AI_RESOURCE_IMPROVE_CATALOG_TEXT]))
        resources[AI_RESOURCE_LIMIT_TITLE_60] = bool(raw.get(AI_RESOURCE_LIMIT_TITLE_60, resources[AI_RESOURCE_LIMIT_TITLE_60]))
        resources[AI_RESOURCE_DESCRIPTION_SIZE] = _safe_description_size(raw.get(AI_RESOURCE_DESCRIPTION_SIZE, resources[AI_RESOURCE_DESCRIPTION_SIZE]))
        resources[AI_RESOURCE_ORTHOGRAPHY_GRAMMAR] = bool(raw.get(AI_RESOURCE_ORTHOGRAPHY_GRAMMAR, resources[AI_RESOURCE_ORTHOGRAPHY_GRAMMAR]))
        resources[AI_RESOURCE_MARKETPLACE_TEXT_GUARD] = bool(raw.get(AI_RESOURCE_MARKETPLACE_TEXT_GUARD, resources[AI_RESOURCE_MARKETPLACE_TEXT_GUARD]))
        resources[AI_RESOURCE_OUT_OF_CONTEXT_FILTER] = bool(raw.get(AI_RESOURCE_OUT_OF_CONTEXT_FILTER, resources[AI_RESOURCE_OUT_OF_CONTEXT_FILTER]))
        resources[AI_RESOURCE_BLOCKED_TERMS] = _safe_multiline_text(raw.get(AI_RESOURCE_BLOCKED_TERMS, resources[AI_RESOURCE_BLOCKED_TERMS]), DEFAULT_BLOCKED_TERMS_TEXT)
        resources[AI_RESOURCE_CONTEXT_FILTER_TERMS] = _safe_multiline_text(raw.get(AI_RESOURCE_CONTEXT_FILTER_TERMS, resources[AI_RESOURCE_CONTEXT_FILTER_TERMS]), DEFAULT_CONTEXT_FILTER_TERMS_TEXT)
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


def marketplace_blocked_terms(resources: dict[str, Any] | None = None) -> list[str]:
    current = normalize_ai_resources(resources if resources is not None else get_ai_resources())
    return _terms_from_text(current.get(AI_RESOURCE_BLOCKED_TERMS, ''))


def marketplace_context_filter_terms(resources: dict[str, Any] | None = None) -> list[str]:
    current = normalize_ai_resources(resources if resources is not None else get_ai_resources())
    return _terms_from_text(current.get(AI_RESOURCE_CONTEXT_FILTER_TERMS, ''))


__all__ = [
    'AI_RESOURCE_BLOCKED_TERMS',
    'AI_RESOURCE_CONTEXT_FILTER_TERMS',
    'AI_RESOURCE_DESCRIPTION_SIZE',
    'AI_RESOURCE_IMPROVE_CATALOG_TEXT',
    'AI_RESOURCE_LIMIT_TITLE_60',
    'AI_RESOURCE_MARKETPLACE_TEXT_GUARD',
    'AI_RESOURCE_ORTHOGRAPHY_GRAMMAR',
    'AI_RESOURCE_OUT_OF_CONTEXT_FILTER',
    'AI_RESOURCE_SUGGEST_NCM',
    'DESCRIPTION_SIZE_OPTIONS',
    'ai_description_size',
    'ai_resource_enabled',
    'get_ai_resources',
    'marketplace_blocked_terms',
    'marketplace_context_filter_terms',
    'normalize_ai_resources',
    'set_ai_resources',
]
