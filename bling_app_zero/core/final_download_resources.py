from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from bling_app_zero.core.gtin import clean_gtin, looks_like_gtin_column
from bling_app_zero.core.text import clean_cell, normalize_key

RESPONSIBLE_FILE = 'bling_app_zero/core/final_download_resources.py'

IMAGE_COLUMN_TERMS = (
    'imagem', 'imagens', 'image', 'images', 'foto', 'fotos',
    'url imagem', 'url imagens', 'url imagens externas',
)
PRODUCT_CODE_COLUMN_TERMS = (
    'codigo', 'código', 'codigo produto', 'código produto', 'codigo do produto',
    'código do produto', 'cod fornecedor', 'cód fornecedor', 'cod no fornecedor',
    'cód no fornecedor', 'codigo no fornecedor', 'código no fornecedor', 'sku',
    'referencia', 'referência',
)
PRODUCT_NAME_COLUMN_TERMS = ('descricao', 'descrição', 'nome', 'produto', 'titulo', 'título')
STOCK_QUANTITY_COLUMN_TERMS = ('balanco', 'balanço', 'saldo', 'estoque', 'quantidade', 'qtd')
AVAILABLE_PATTERNS = ('disponivel', 'disponível', 'em estoque', 'produto disponivel', 'produto disponível', 'in stock', 'available')
LOW_PATTERNS = ('baixo', 'baixo estoque', 'estoque baixo', 'poucas unidades', 'ultimas unidades', 'últimas unidades', 'low stock')
OUT_PATTERNS = ('esgotado', 'sem estoque', 'indisponivel', 'indisponível', 'zerado', 'out of stock', 'unavailable')
EMPTY_TEXT_KEYS = {'', 'nan', 'none', 'null', 'na', 'n/a', 'nao informado', 'naoinformado', 'sem informacao', 'seminformacao'}


@dataclass(frozen=True)
class ResourceResult:
    df: pd.DataFrame
    changed: int = 0
    columns: tuple[str, ...] = ()
    message: str = ''


def _df(df: pd.DataFrame | None) -> pd.DataFrame:
    return df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()


def _normalized_terms(terms: Iterable[str]) -> set[str]:
    return {normalize_key(term) for term in terms}


def looks_like_image_column(column: object) -> bool:
    key = normalize_key(column)
    return any(normalize_key(term) in key for term in IMAGE_COLUMN_TERMS)


def looks_like_stock_quantity_column(column: object) -> bool:
    key = normalize_key(column)
    return any(normalize_key(term) in key for term in STOCK_QUANTITY_COLUMN_TERMS)


def looks_like_product_code_column(column: object) -> bool:
    key = normalize_key(column)
    if not key or looks_like_gtin_column(column):
        return False
    return key in _normalized_terms(PRODUCT_CODE_COLUMN_TERMS)


def looks_like_product_name_column(column: object) -> bool:
    key = normalize_key(column)
    return key in _normalized_terms(PRODUCT_NAME_COLUMN_TERMS)


def is_empty_text(value: object) -> bool:
    text = clean_cell(value).strip()
    if not text:
        return True
    return normalize_key(text) in EMPTY_TEXT_KEYS


def normalize_image_urls(value: object) -> str:
    text = clean_cell(value)
    if not text:
        return ''
    raw_parts = re.split(r'\s*\|\s*|\s*[\n\r,;]+\s*', text)
    parts: list[str] = []
    seen: set[str] = set()
    for raw in raw_parts:
        item = clean_cell(raw).strip().strip('"\'[]()')
        if not item or not item.lower().startswith(('http://', 'https://')) or item in seen:
            continue
        seen.add(item)
        parts.append(item)
    return '|'.join(parts)


def clean_cells_resource(df: pd.DataFrame | None) -> ResourceResult:
    out = _df(df)
    if out.empty:
        return ResourceResult(out, message='Sem dados para limpeza textual.')
    out.columns = [clean_cell(column) for column in out.columns]
    for column in out.columns:
        out[column] = out[column].apply(clean_cell)
    return ResourceResult(out, changed=len(out) * len(out.columns), columns=tuple(map(str, out.columns)), message='Células e nomes de colunas limpos.')


def clean_invalid_gtin_resource(df: pd.DataFrame | None, *, enabled: bool = True) -> ResourceResult:
    out = _df(df)
    if out.empty or not enabled:
        return ResourceResult(out, message='Limpeza de GTIN desativada ou sem dados.')
    changed = 0
    columns: list[str] = []
    for column in out.columns:
        if looks_like_gtin_column(column):
            columns.append(str(column))
            before = out[column].astype(str).tolist()
            out[column] = out[column].apply(clean_gtin)
            changed += sum(1 for old, new in zip(before, out[column].astype(str).tolist()) if old != new)
    return ResourceResult(out, changed=changed, columns=tuple(columns), message=f'GTIN limpo em {changed} célula(s).')


def normalize_image_separator_resource(df: pd.DataFrame | None, *, enabled: bool = True) -> ResourceResult:
    out = _df(df)
    if out.empty or not enabled:
        return ResourceResult(out, message='Normalização de imagens desativada ou sem dados.')
    columns = [str(column) for column in out.columns if looks_like_image_column(column)]
    for column in columns:
        out[column] = out[column].apply(normalize_image_urls)
    return ResourceResult(out, changed=len(columns), columns=tuple(columns), message=f'Imagens normalizadas em {len(columns)} coluna(s).')


def stock_status_to_quantity(value: object, defaults: dict[str, str] | None = None) -> str:
    text = clean_cell(value)
    if not text:
        return ''
    key = normalize_key(text)
    defaults = dict(defaults or {})
    if any(normalize_key(pattern) in key for pattern in OUT_PATTERNS):
        return str(defaults.get('esgotado', '0'))
    if any(normalize_key(pattern) in key for pattern in LOW_PATTERNS):
        return str(defaults.get('baixo', '0'))
    if any(normalize_key(pattern) in key for pattern in AVAILABLE_PATTERNS):
        return str(defaults.get('disponivel', '1000'))
    return text


def normalize_stock_status_resource(df: pd.DataFrame | None, *, defaults: dict[str, str] | None = None) -> ResourceResult:
    out = _df(df)
    if out.empty:
        return ResourceResult(out, message='Sem dados para status de estoque.')
    changed = 0
    columns = [str(column) for column in out.columns if looks_like_stock_quantity_column(column)]
    for column in columns:
        before = out[column].astype(str).tolist()
        out[column] = out[column].apply(lambda value: stock_status_to_quantity(value, defaults))
        changed += sum(1 for old, new in zip(before, out[column].astype(str).tolist()) if old != new)
    return ResourceResult(out, changed=changed, columns=tuple(columns), message=f'Status de estoque convertidos em {changed} célula(s).')


def safe_code_text(value: object) -> str:
    text = clean_cell(value)
    text = re.sub(r'\s+', '-', text)
    text = re.sub(r'[^A-Za-z0-9._-]+', '', text)
    text = re.sub(r'-+', '-', text).strip('-._')
    return text[:60]


def gtin_code_from_row(df: pd.DataFrame, row_index: int) -> str:
    out = _df(df)
    for column in out.columns:
        if looks_like_gtin_column(column):
            value = clean_gtin(out.at[row_index, column]) if row_index in out.index else ''
            if value:
                return value[:60]
    return ''


def fallback_code_from_row(df: pd.DataFrame, row_index: int, *, auto_product_code: bool = True) -> str:
    if not auto_product_code:
        return ''
    out = _df(df)
    gtin_code = gtin_code_from_row(out, row_index)
    if gtin_code:
        return gtin_code
    for column in [c for c in out.columns if looks_like_product_name_column(c)]:
        value = clean_cell(out.at[row_index, column]) if row_index in out.index else ''
        key = normalize_key(value)
        if key:
            base = re.sub(r'[^a-z0-9]+', '', key)[:24]
            if base:
                return f'auto-{base}-{row_index + 1}'[:60]
    return f'auto-{row_index + 1}'


def make_unique_code(base_code: str, row_index: int, seen: set[str], *, auto_product_code: bool = True, unique_product_code: bool = True) -> str:
    base = safe_code_text(base_code)
    if not base and auto_product_code:
        base = f'auto-{row_index + 1}'
    if not base:
        return ''
    candidate = base[:60]
    if not unique_product_code:
        return candidate
    counter = 2
    while normalize_key(candidate) in seen:
        suffix = f'-{counter}'
        candidate = f'{base[:60 - len(suffix)]}{suffix}'
        counter += 1
    return candidate


def unique_product_codes_resource(
    df: pd.DataFrame | None,
    *,
    auto_product_code: bool = True,
    unique_product_code: bool = True,
) -> ResourceResult:
    out = _df(df)
    if out.empty:
        return ResourceResult(out, message='Sem dados para código automático.')
    changed = 0
    columns = [str(column) for column in out.columns if looks_like_product_code_column(column)]
    for column in columns:
        seen: set[str] = set()
        values: list[str] = []
        before = out[column].astype(str).tolist()
        for position, row_index in enumerate(out.index):
            base_code = safe_code_text(out.at[row_index, column])
            if not base_code:
                base_code = fallback_code_from_row(out, row_index, auto_product_code=auto_product_code)
            unique_code = make_unique_code(
                base_code,
                position,
                seen,
                auto_product_code=auto_product_code,
                unique_product_code=unique_product_code,
            )
            if unique_code:
                seen.add(normalize_key(unique_code))
            values.append(unique_code)
        out[column] = values
        changed += sum(1 for old, new in zip(before, out[column].astype(str).tolist()) if old != new)
    return ResourceResult(out, changed=changed, columns=tuple(columns), message='Códigos de produto normalizados e deduplicados.')


__all__ = [
    'AVAILABLE_PATTERNS',
    'EMPTY_TEXT_KEYS',
    'IMAGE_COLUMN_TERMS',
    'LOW_PATTERNS',
    'OUT_PATTERNS',
    'PRODUCT_CODE_COLUMN_TERMS',
    'PRODUCT_NAME_COLUMN_TERMS',
    'RESPONSIBLE_FILE',
    'ResourceResult',
    'STOCK_QUANTITY_COLUMN_TERMS',
    'clean_cells_resource',
    'clean_invalid_gtin_resource',
    'fallback_code_from_row',
    'gtin_code_from_row',
    'is_empty_text',
    'looks_like_image_column',
    'looks_like_product_code_column',
    'looks_like_product_name_column',
    'looks_like_stock_quantity_column',
    'make_unique_code',
    'normalize_image_separator_resource',
    'normalize_image_urls',
    'normalize_stock_status_resource',
    'safe_code_text',
    'stock_status_to_quantity',
    'unique_product_codes_resource',
]
