from __future__ import annotations

import importlib
import re
from collections.abc import MutableMapping
from typing import Any

import pandas as pd

from bling_app_zero.core.text import clean_cell, normalize_key

NORMALIZE_MEASURES_RESOURCE_KEY = 'resource_normalize_measures_to_meters'
CENTRAL_RULES_SESSION_KEY = 'bling_user_rules'
CENTRAL_NORMALIZE_MEASURES_KEY = 'normalize_measures_to_meters'
_FALLBACK_STATE: dict[str, Any] = {}

_MEASURE_TERMS = {
    'altura',
    'largura',
    'comprimento',
    'profundidade',
}

_NEGATIVE_TERMS = {
    'peso',
    'preco',
    'preço',
    'valor',
    'quantidade',
    'estoque',
    'saldo',
    'gtin',
    'ean',
    'sku',
    'codigo',
    'código',
}


def _streamlit_module() -> Any | None:
    try:
        return importlib.import_module('streamlit')
    except Exception:
        return None


def state_store(state: MutableMapping[str, Any] | None = None) -> MutableMapping[str, Any]:
    if state is not None:
        return state
    st = _streamlit_module()
    if st is not None:
        try:
            return st.session_state
        except Exception:
            pass
    return _FALLBACK_STATE


def normalize_measures_resource_enabled(default: bool = False, *, state: MutableMapping[str, Any] | None = None) -> bool:
    """Lê o recurso pela mesma chave central que o exportador usa.

    Mantém compatibilidade com a chave antiga da UI para sessões abertas antes
    deste BLINGSCAN, mas a fonte principal passa a ser bling_user_rules.
    """
    store = state_store(state)
    try:
        rules = store.get(CENTRAL_RULES_SESSION_KEY)
        if isinstance(rules, dict) and CENTRAL_NORMALIZE_MEASURES_KEY in rules:
            return bool(rules.get(CENTRAL_NORMALIZE_MEASURES_KEY, default))
        return bool(store.get(NORMALIZE_MEASURES_RESOURCE_KEY, default))
    except Exception:
        return bool(default)


def looks_like_dimension_column(column: Any) -> bool:
    """Detecta somente colunas de dimensão física do produto.

    A regra é conservadora para não mexer em preço, estoque, peso, GTIN, SKU
    ou outros campos numéricos.
    """
    key = normalize_key(column)
    if not key:
        return False
    if any(term in key for term in _NEGATIVE_TERMS):
        return False
    return any(term in key for term in _MEASURE_TERMS)


def _extract_numeric_text(value: Any) -> str:
    text = clean_cell(value).strip().lower()
    if not text:
        return ''
    match = re.search(r'-?\d+(?:[\.,]\d+)*', text)
    return match.group(0) if match else ''


def _parse_number(value: Any) -> float | None:
    numeric = _extract_numeric_text(value)
    if not numeric:
        return None

    if ',' in numeric and '.' in numeric:
        if numeric.rfind(',') > numeric.rfind('.'):
            numeric = numeric.replace('.', '').replace(',', '.')
        else:
            numeric = numeric.replace(',', '')
    elif ',' in numeric:
        numeric = numeric.replace(',', '.')

    try:
        return float(numeric)
    except Exception:
        return None


def _format_measure_ptbr(number: float) -> str:
    if abs(number) == 0:
        return '0,00'
    return f'{number:.3f}'.replace('.', ',')


def normalize_measure_value_to_meters(value: Any) -> str:
    """Converte medidas inteiras em milímetros para metros.

    Exemplos:
    - 18 -> 0,018
    - 676 -> 0,676
    - 0,676 -> 0,676
    - 0,00 -> 0,00
    """
    text = clean_cell(value).strip()
    if not text:
        return ''

    number = _parse_number(text)
    if number is None:
        return text

    if abs(number) >= 1:
        number = number / 1000

    return _format_measure_ptbr(number)


def normalize_measure_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    out = df.copy()
    for column in out.columns:
        if looks_like_dimension_column(column):
            out[column] = out[column].apply(normalize_measure_value_to_meters)
    return out


__all__ = [
    'CENTRAL_NORMALIZE_MEASURES_KEY',
    'CENTRAL_RULES_SESSION_KEY',
    'NORMALIZE_MEASURES_RESOURCE_KEY',
    'looks_like_dimension_column',
    'normalize_measure_columns',
    'normalize_measure_value_to_meters',
    'normalize_measures_resource_enabled',
    'state_store',
]
