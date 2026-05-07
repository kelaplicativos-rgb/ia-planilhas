from __future__ import annotations

import re
from io import BytesIO

import pandas as pd

from bling_app_zero.core.gtin import clean_gtin, looks_like_gtin_column
from bling_app_zero.core.text import clean_cell, normalize_key

IMAGE_COLUMN_TERMS = [
    'imagem',
    'imagens',
    'image',
    'images',
    'foto',
    'fotos',
    'url imagem',
    'url imagens',
    'url imagens externas',
]

PRODUCT_CODE_COLUMN_TERMS = [
    'codigo',
    'código',
    'codigo produto',
    'código produto',
    'codigo do produto',
    'código do produto',
    'sku',
    'referencia',
    'referência',
]


def _looks_like_image_column(column: object) -> bool:
    key = str(column or '').strip().lower()
    return any(term in key for term in IMAGE_COLUMN_TERMS)


def _looks_like_product_code_column(column: object) -> bool:
    key = normalize_key(column)
    if not key:
        return False
    if looks_like_gtin_column(column):
        return False
    return key in {normalize_key(term) for term in PRODUCT_CODE_COLUMN_TERMS}


def normalize_image_urls(value: object) -> str:
    text = clean_cell(value)
    if not text:
        return ''

    raw_parts = re.split(r'\s*\|\s*|\s*[\n\r,;]+\s*', text)
    parts: list[str] = []
    seen: set[str] = set()

    for raw in raw_parts:
        item = clean_cell(raw).strip().strip('"\'[]()')
        if not item:
            continue
        if not item.lower().startswith(('http://', 'https://')):
            continue
        if item in seen:
            continue
        seen.add(item)
        parts.append(item)

    return '|'.join(parts)


def _blank_duplicate_product_codes(out: pd.DataFrame) -> pd.DataFrame:
    if out is None or out.empty:
        return out

    code_columns = [column for column in out.columns if _looks_like_product_code_column(column)]
    for column in code_columns:
        seen: set[str] = set()
        cleaned_values: list[str] = []

        for value in out[column].tolist():
            text = clean_cell(value)
            key = normalize_key(text)
            if not key:
                cleaned_values.append('')
                continue
            if key in seen:
                cleaned_values.append('')
                continue
            seen.add(key)
            cleaned_values.append(text)

        out[column] = cleaned_values

    return out


def sanitize_for_bling(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()

    out = df.copy().fillna('')

    for col in out.columns:
        if looks_like_gtin_column(col):
            out[col] = out[col].apply(clean_gtin)
        elif _looks_like_image_column(col):
            out[col] = out[col].apply(normalize_image_urls)
        else:
            out[col] = out[col].apply(clean_cell)

    out = _blank_duplicate_product_codes(out)
    return out.fillna('')


def to_bling_csv_bytes(df: pd.DataFrame) -> bytes:
    safe = sanitize_for_bling(df)
    buffer = BytesIO()
    safe.to_csv(buffer, sep=';', index=False, encoding='utf-8-sig')
    return buffer.getvalue()


def filename_for_operation(operation: str) -> str:
    op = str(operation or 'bling').lower().strip()
    if op == 'estoque':
        return 'bling_atualizacao_estoque.csv'
    if op == 'cadastro':
        return 'bling_cadastro_produtos.csv'
    return 'bling_exportacao.csv'
