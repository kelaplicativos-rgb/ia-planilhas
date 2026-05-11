from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from bling_app_zero.core.ai_resource_rules import (
    AI_RESOURCE_MARKETPLACE_TEXT_GUARD,
    AI_RESOURCE_OUT_OF_CONTEXT_FILTER,
    marketplace_blocked_terms,
    marketplace_context_filter_terms,
)
from bling_app_zero.core.text import clean_cell, normalize_key

TITLE_CANDIDATES = [
    'Descrição',
    'Descricao',
    'Descrição do produto',
    'Descricao do produto',
    'Nome',
    'Nome do produto',
    'Produto',
    'Título',
    'Titulo',
]

DESCRIPTION_CANDIDATES = [
    'Descrição complementar',
    'Descricao complementar',
    'Descrição completa',
    'Descricao completa',
    'Complementar',
    'Descrição longa',
    'Descricao longa',
    'Descrição detalhada',
    'Descricao detalhada',
]

DEFAULT_BLOCKED_TERMS = [
    'réplica',
    'replica',
    'primeira linha',
    'garantia vitalícia',
    'garantia vitalicia',
    '100% garantido',
    'melhor do mercado',
    'produto original',
    'original samsung',
    'original apple',
    'original xiaomi',
    'anvisa',
    'medicamento',
    'arma',
    'armas',
]

DEFAULT_CONTEXT_TERMS = [
    'aqui você coloca a descrição',
    'aqui voce coloca a descricao',
    'descrição do produto aqui',
    'descricao do produto aqui',
    'coloque aqui',
    'insira aqui',
    'texto exemplo',
    'lorem ipsum',
    'adicione a descrição',
    'adicione a descricao',
]


@dataclass(frozen=True)
class MarketplaceTextAlert:
    row_number: int
    column: str
    issue_type: str
    term: str
    value_preview: str


def _find_first_column(df: pd.DataFrame, candidates: list[str]) -> str:
    normalized_columns = {normalize_key(str(column)): str(column) for column in df.columns}
    for candidate in candidates:
        key = normalize_key(candidate)
        if key in normalized_columns:
            return normalized_columns[key]
    for column in df.columns:
        key = normalize_key(str(column))
        if any(normalize_key(candidate) in key for candidate in candidates):
            return str(column)
    return ''


def detect_text_columns(df: pd.DataFrame) -> dict[str, str]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return {'title': '', 'description': ''}
    return {
        'title': _find_first_column(df, TITLE_CANDIDATES),
        'description': _find_first_column(df, DESCRIPTION_CANDIDATES),
    }


def _unique_terms(*term_groups: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for group in term_groups:
        for term in group:
            clean = clean_cell(term)
            key = normalize_key(clean)
            if clean and key not in seen:
                result.append(clean)
                seen.add(key)
    return result


def _contains_term(text: str, term: str) -> bool:
    if not text or not term:
        return False
    return normalize_key(term) in normalize_key(text)


def _preview(value: str, limit: int = 160) -> str:
    text = clean_cell(value)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + '...'


def _enabled(resources: dict[str, Any], key: str) -> bool:
    return bool(resources.get(key, False))


def analyze_marketplace_text(df: pd.DataFrame, resources: dict[str, Any]) -> list[MarketplaceTextAlert]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []

    marketplace_guard = _enabled(resources, AI_RESOURCE_MARKETPLACE_TEXT_GUARD)
    context_filter = _enabled(resources, AI_RESOURCE_OUT_OF_CONTEXT_FILTER)
    if not marketplace_guard and not context_filter:
        return []

    columns = detect_text_columns(df)
    watched_columns = [column for column in [columns.get('title'), columns.get('description')] if column]
    if not watched_columns:
        return []

    blocked_terms = _unique_terms(DEFAULT_BLOCKED_TERMS, marketplace_blocked_terms(resources))
    context_terms = _unique_terms(DEFAULT_CONTEXT_TERMS, marketplace_context_filter_terms(resources))

    alerts: list[MarketplaceTextAlert] = []
    for index, row in df.iterrows():
        row_number = int(index) + 1 if isinstance(index, int) else len(alerts) + 1
        for column in watched_columns:
            value = clean_cell(row.get(column, ''))
            if not value:
                continue
            if marketplace_guard:
                for term in blocked_terms:
                    if _contains_term(value, term):
                        alerts.append(MarketplaceTextAlert(row_number, column, 'Palavra proibida/sensível', term, _preview(value)))
            if context_filter:
                for term in context_terms:
                    if _contains_term(value, term):
                        alerts.append(MarketplaceTextAlert(row_number, column, 'Descrição fora de contexto', term, _preview(value)))
    return alerts[:300]


def alerts_to_dataframe(alerts: list[MarketplaceTextAlert]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            'Linha': alert.row_number,
            'Coluna': alert.column,
            'Tipo': alert.issue_type,
            'Termo detectado': alert.term,
            'Trecho': alert.value_preview,
        }
        for alert in alerts
    ])


__all__ = ['MarketplaceTextAlert', 'alerts_to_dataframe', 'analyze_marketplace_text', 'detect_text_columns']
