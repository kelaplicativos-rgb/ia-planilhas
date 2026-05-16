from __future__ import annotations

import re
from typing import Any

import pandas as pd

MAX_SAMPLE_ROWS = 12
PRICE_RE = re.compile(r'^(?:R\$\s*)?-?\d{1,3}(?:\.\d{3})*,\d{1,2}$|^(?:R\$\s*)?-?\d+(?:[,.]\d{1,2})?$', re.IGNORECASE)
GTIN_RE = re.compile(r'^\d{8}$|^\d{12}$|^\d{13}$|^\d{14}$')
URL_RE = re.compile(r'^https?://', re.IGNORECASE)
INT_RE = re.compile(r'^-?\d+$')


def normalize_text(value: object) -> str:
    return ' '.join(str(value or '').replace('\xa0', ' ').split()).strip()


def normalize_column_name(value: object) -> str:
    text = normalize_text(value).lower()
    replacements = {
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a',
        'é': 'e', 'ê': 'e',
        'í': 'i',
        'ó': 'o', 'õ': 'o', 'ô': 'o',
        'ú': 'u',
        'ç': 'c',
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()


def sample_column_values(df: pd.DataFrame, column: str, limit: int = MAX_SAMPLE_ROWS) -> list[str]:
    if not isinstance(df, pd.DataFrame) or column not in df.columns:
        return []
    values = []
    for value in df[column].dropna().astype(str).tolist():
        clean = normalize_text(value)
        if clean and clean not in values:
            values.append(clean[:180])
        if len(values) >= limit:
            break
    return values


def detect_value_kind(values: list[str]) -> str:
    clean_values = [normalize_text(value) for value in values if normalize_text(value)]
    if not clean_values:
        return 'vazio'
    total = len(clean_values)
    url_count = sum(1 for value in clean_values if URL_RE.search(value))
    gtin_count = sum(1 for value in clean_values if GTIN_RE.search(re.sub(r'\D', '', value)))
    price_count = sum(1 for value in clean_values if PRICE_RE.search(value))
    int_count = sum(1 for value in clean_values if INT_RE.search(value))
    long_text_count = sum(1 for value in clean_values if len(value) > 80)

    if url_count / total >= 0.6:
        return 'url'
    if gtin_count / total >= 0.6:
        return 'gtin'
    if price_count / total >= 0.6:
        return 'preco'
    if int_count / total >= 0.7:
        return 'inteiro'
    if long_text_count / total >= 0.5:
        return 'texto_longo'
    return 'texto_curto'


def profile_dataframe_columns(df: pd.DataFrame, *, max_columns: int = 80) -> list[dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    profiles: list[dict[str, Any]] = []
    for column in list(df.columns)[:max_columns]:
        samples = sample_column_values(df, str(column))
        profiles.append(
            {
                'column': str(column),
                'normalized_column': normalize_column_name(column),
                'detected_value_kind': detect_value_kind(samples),
                'sample_values': samples,
                'non_empty_count': int(df[column].astype(str).map(lambda value: bool(normalize_text(value))).sum()),
            }
        )
    return profiles


def dataframe_snapshot(df: pd.DataFrame, *, max_rows: int = 8, max_columns: int = 40) -> dict[str, Any]:
    if not isinstance(df, pd.DataFrame):
        return {'columns': [], 'rows': [], 'shape': [0, 0], 'profiles': []}
    limited = df.copy().fillna('').astype(str).iloc[:max_rows, :max_columns]
    return {
        'columns': [str(column) for column in df.columns[:max_columns]],
        'rows': limited.to_dict(orient='records'),
        'shape': [int(len(df)), int(len(df.columns))],
        'profiles': profile_dataframe_columns(df, max_columns=max_columns),
    }


__all__ = [
    'dataframe_snapshot',
    'detect_value_kind',
    'normalize_column_name',
    'normalize_text',
    'profile_dataframe_columns',
    'sample_column_values',
]
