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

PRODUCT_NAME_COLUMN_TERMS = [
    'descricao',
    'descrição',
    'nome',
    'produto',
    'titulo',
    'título',
]

DEFAULT_MEASURES_CM = {
    'altura': '2',
    'comprimento': '18',
    'largura': '11',
}


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


def _looks_like_product_name_column(column: object) -> bool:
    key = normalize_key(column)
    return key in {normalize_key(term) for term in PRODUCT_NAME_COLUMN_TERMS}


def _measure_kind(column: object) -> str:
    key = normalize_key(column)
    if not key:
        return ''
    if 'altura' in key:
        return 'altura'
    if 'comprimento' in key:
        return 'comprimento'
    if 'largura' in key:
        return 'largura'
    return ''


def _is_empty_measure(value: object) -> bool:
    text = clean_cell(value).strip()
    if not text:
        return True
    key = normalize_key(text)
    return key in {'nan', 'none', 'null', 'nao informado', 'naoinformado', 'sem medida', 'semmedida'}


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


def _safe_code_text(value: object) -> str:
    text = clean_cell(value)
    text = re.sub(r'\s+', '', text)
    text = re.sub(r'[^A-Za-z0-9._-]+', '', text)
    return text[:60]


def _gtin_code_from_row(out: pd.DataFrame, row_index: int) -> str:
    for column in out.columns:
        if not looks_like_gtin_column(column):
            continue
        value = clean_gtin(out.at[row_index, column]) if row_index in out.index else ''
        if value:
            return value[:60]
    return ''


def _fallback_code_from_row(out: pd.DataFrame, row_index: int) -> str:
    gtin_code = _gtin_code_from_row(out, row_index)
    if gtin_code:
        return gtin_code

    name_columns = [column for column in out.columns if _looks_like_product_name_column(column)]
    for column in name_columns:
        value = clean_cell(out.at[row_index, column]) if row_index in out.index else ''
        key = normalize_key(value)
        if key:
            base = re.sub(r'[^a-z0-9]+', '', key)[:24]
            if base:
                return f'auto{base}{row_index + 1}'[:60]
    return f'auto{row_index + 1}'


def _make_unique_code(base_code: str, row_index: int, seen: set[str]) -> str:
    base = _safe_code_text(base_code) or f'auto{row_index + 1}'
    candidate = base[:60]
    counter = 2

    while normalize_key(candidate) in seen:
        suffix = f'-{counter}'
        candidate = f'{base[:60 - len(suffix)]}{suffix}'
        counter += 1

    return candidate


def _ensure_unique_product_codes(out: pd.DataFrame) -> pd.DataFrame:
    if out is None or out.empty:
        return out

    code_columns = [column for column in out.columns if _looks_like_product_code_column(column)]
    for column in code_columns:
        seen: set[str] = set()
        cleaned_values: list[str] = []

        for position, row_index in enumerate(out.index):
            original = clean_cell(out.at[row_index, column])
            base_code = _safe_code_text(original)
            if not base_code:
                base_code = _fallback_code_from_row(out, row_index)

            unique_code = _make_unique_code(base_code, position, seen)
            seen.add(normalize_key(unique_code))
            cleaned_values.append(unique_code)

        out[column] = cleaned_values

    return out


def _fill_default_measures(out: pd.DataFrame) -> pd.DataFrame:
    if out is None or out.empty:
        return out

    for column in out.columns:
        kind = _measure_kind(column)
        if not kind:
            continue
        default_value = DEFAULT_MEASURES_CM[kind]
        out[column] = out[column].apply(lambda value: default_value if _is_empty_measure(value) else clean_cell(value))

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

    out = _fill_default_measures(out)
    out = _ensure_unique_product_codes(out)
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
