from __future__ import annotations

import re
from typing import Any

import pandas as pd

RESPONSIBLE_FILE = 'bling_app_zero/core/verified_error_context.py'
SKU_COLUMN_HINTS = (
    'sku', 'codigo', 'código', 'codigo produto', 'código produto', 'codigo do produto', 'código do produto',
    'cod', 'ref', 'referencia', 'referência', 'id produto', 'id bling', 'gtin', 'ean', 'codigo de barras', 'código de barras',
)
PRODUCT_COLUMN_HINTS = ('nome', 'produto', 'descricao', 'descrição', 'titulo', 'título', 'nome produto', 'nome do produto')


def _norm(value: Any) -> str:
    text = str(value or '').strip().lower()
    for old, new in {'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c'}.items():
        text = text.replace(old, new)
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', text)).strip()


def _safe_text(value: Any, *, limit: int = 120) -> str:
    if value is None:
        return ''
    try:
        if pd.isna(value):
            return ''
    except Exception:
        pass
    text = re.sub(r'\s+', ' ', str(value or '').strip())
    return text[:limit]


def _line_from_error(error: str) -> int | None:
    match = re.search(r'linha\s+(\d+)', str(error or ''), flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def _row_for_line(df: pd.DataFrame, line: int | None) -> pd.Series | None:
    if not isinstance(df, pd.DataFrame) or df.empty or not line:
        return None
    index_value = line - 1
    if index_value in df.index:
        try:
            return df.loc[index_value]
        except Exception:
            pass
    position = max(0, min(len(df) - 1, index_value))
    try:
        return df.iloc[position]
    except Exception:
        return None


def _first_value_by_hints(row: pd.Series | None, hints: tuple[str, ...], *, limit: int = 120) -> str:
    if row is None:
        return ''
    normalized_hints = {_norm(item) for item in hints}
    try:
        items = row.items()
    except Exception:
        return ''
    for column, value in items:
        key = _norm(column)
        if key in normalized_hints or any(hint in key for hint in normalized_hints):
            text = _safe_text(value, limit=limit)
            if text:
                return text
    return ''


def enrich_verified_error(error: str, df: pd.DataFrame) -> str:
    text = str(error or '').strip()
    if not text:
        return text
    lowered = text.lower()
    if 'sku/código' in lowered or 'sku/codigo' in lowered or 'produto:' in lowered:
        return text
    line = _line_from_error(text)
    row = _row_for_line(df, line)
    sku = _first_value_by_hints(row, SKU_COLUMN_HINTS, limit=80)
    product = _first_value_by_hints(row, PRODUCT_COLUMN_HINTS, limit=120)
    if not sku and not product:
        return text
    details: list[str] = []
    if sku:
        details.append(f'SKU/Código: {sku}')
    if product:
        details.append(f'Produto: {product}')
    clean = re.sub(r'^linha\s+\d+\s*:\s*', '', text, flags=re.IGNORECASE)
    prefix = f'Linha {line}' if line else 'Linha'
    return f'{prefix} · ' + ' · '.join(details) + f': {clean}'


def enrich_verified_errors(errors: tuple[str, ...] | list[str], df: pd.DataFrame) -> tuple[str, ...]:
    return tuple(enrich_verified_error(error, df) for error in tuple(errors or ()))


__all__ = ['RESPONSIBLE_FILE', 'enrich_verified_error', 'enrich_verified_errors']
