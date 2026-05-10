from __future__ import annotations

import re
from io import BytesIO
from typing import Any

import pandas as pd

from bling_app_zero.core.gtin import clean_gtin, looks_like_gtin_column
from bling_app_zero.core.text import clean_cell, normalize_key
from bling_app_zero.core.user_rules import custom_rules_from_rules, get_user_rules, measure_defaults_from_rules

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
    'cod fornecedor',
    'cód fornecedor',
    'cod no fornecedor',
    'cód no fornecedor',
    'codigo no fornecedor',
    'código no fornecedor',
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
    'largura': '11',
    'profundidade': '18',
    'comprimento': '18',
}

DEFAULT_SUPPLIER = 'Não definido'
DEFAULT_MEASURE_UNIT = 'Centímetro'
SUPPLIER_INVALID_KEYS = {
    '',
    'nan',
    'none',
    'null',
    'na',
    'n/a',
    'nao informado',
    'naoinformado',
    'sem informacao',
    'seminformacao',
    'indefinido',
    'undefined',
}
SUPPLIER_CODE_RE = re.compile(r'^[A-Za-z]{0,6}\d+[A-Za-z0-9._/-]*$')


def _looks_like_image_column(column: object) -> bool:
    key = normalize_key(column)
    return any(normalize_key(term) in key for term in IMAGE_COLUMN_TERMS)


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


def _looks_like_supplier_column(column: object) -> bool:
    key = normalize_key(column)
    return key in {'fornecedor', 'nome fornecedor', 'nome do fornecedor', 'supplier'}


def _looks_like_measure_unit_column(column: object) -> bool:
    key = normalize_key(column)
    return key in {'unidade de medida', 'unidade medida', 'unidade das medidas', 'unidade dimensoes', 'unidade dimensoes produto'}


def _measure_kind(column: object) -> str:
    key = normalize_key(column)
    if not key:
        return ''
    if 'altura' in key:
        return 'altura'
    if 'largura' in key:
        return 'largura'
    if 'profundidade' in key:
        return 'profundidade'
    if 'comprimento' in key:
        return 'comprimento'
    return ''


def _is_empty_text(value: object) -> bool:
    text = clean_cell(value).strip()
    if not text:
        return True
    key = normalize_key(text)
    return key in {'nan', 'none', 'null', 'na', 'n/a', 'nao informado', 'naoinformado', 'sem informacao', 'seminformacao'}


def _is_invalid_supplier_value(value: object) -> bool:
    text = clean_cell(value).strip()
    key = normalize_key(text)
    if key in SUPPLIER_INVALID_KEYS:
        return True
    if len(text) <= 2:
        return True
    if text.startswith(('http://', 'https://')):
        return True
    if SUPPLIER_CODE_RE.match(text):
        return True
    if re.search(r'\d', text) and not re.search(r'[A-Za-zÀ-ÿ]{3,}\s+[A-Za-zÀ-ÿ]{2,}', text):
        return True
    return False


def _is_empty_measure(value: object) -> bool:
    if _is_empty_text(value):
        return True
    text = clean_cell(value).strip().lower().replace(',', '.')
    numeric = re.sub(r'[^0-9.-]+', '', text)
    if numeric:
        try:
            return float(numeric) == 0.0
        except Exception:
            pass
    key = normalize_key(text)
    return key in {'sem medida', 'semmedida', '0', '0000'}


def _fallback_rules() -> dict[str, Any]:
    return {
        'supplier_default': DEFAULT_SUPPLIER,
        'measure_unit_default': DEFAULT_MEASURE_UNIT,
        'height_default': DEFAULT_MEASURES_CM['altura'],
        'width_default': DEFAULT_MEASURES_CM['largura'],
        'depth_default': DEFAULT_MEASURES_CM['profundidade'],
        'length_default': DEFAULT_MEASURES_CM['comprimento'],
        'invalid_gtin_mode': 'limpar',
        'image_separator': '|',
        'auto_product_code': True,
        'unique_product_code': True,
        'custom_rules': [],
    }


def _rules() -> dict[str, Any]:
    try:
        return get_user_rules()
    except Exception:
        return _fallback_rules()


def _image_separator() -> str:
    return '|'


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

    return _image_separator().join(parts)


def _safe_code_text(value: object) -> str:
    text = clean_cell(value)
    text = re.sub(r'\s+', '-', text)
    text = re.sub(r'[^A-Za-z0-9._-]+', '', text)
    text = re.sub(r'-+', '-', text).strip('-._')
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
    if not bool(_rules().get('auto_product_code', True)):
        return ''

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
                return f'auto-{base}-{row_index + 1}'[:60]
    return f'auto-{row_index + 1}'


def _make_unique_code(base_code: str, row_index: int, seen: set[str]) -> str:
    base = _safe_code_text(base_code)
    if not base and bool(_rules().get('auto_product_code', True)):
        base = f'auto-{row_index + 1}'
    if not base:
        return ''

    candidate = base[:60]
    if not bool(_rules().get('unique_product_code', True)):
        return candidate

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
            if unique_code:
                seen.add(normalize_key(unique_code))
            cleaned_values.append(unique_code)

        out[column] = cleaned_values

    return out


def _fill_default_measures(out: pd.DataFrame) -> pd.DataFrame:
    if out is None or out.empty:
        return out

    defaults = measure_defaults_from_rules(_rules())
    for column in out.columns:
        kind = _measure_kind(column)
        if not kind:
            continue
        default_value = str(defaults.get(kind, DEFAULT_MEASURES_CM.get(kind, '')) or '')
        out[column] = out[column].apply(lambda value: default_value if _is_empty_measure(value) else clean_cell(value))

    return out


def _fill_default_supplier(out: pd.DataFrame) -> pd.DataFrame:
    if out is None or out.empty:
        return out

    supplier_default = str(_rules().get('supplier_default') or DEFAULT_SUPPLIER)
    for column in out.columns:
        if not _looks_like_supplier_column(column):
            continue
        out[column] = out[column].apply(
            lambda value: supplier_default if _is_invalid_supplier_value(value) else clean_cell(value)
        )

    return out


def _fill_measure_unit(out: pd.DataFrame) -> pd.DataFrame:
    if out is None or out.empty:
        return out

    measure_unit = str(_rules().get('measure_unit_default') or DEFAULT_MEASURE_UNIT)
    for column in out.columns:
        if not _looks_like_measure_unit_column(column):
            continue
        out[column] = out[column].apply(lambda value: measure_unit if _is_empty_text(value) else clean_cell(value))

    return out


def _target_column_by_rule(out: pd.DataFrame, target_column: str) -> str:
    target_key = normalize_key(target_column)
    for column in out.columns:
        if normalize_key(column) == target_key:
            return str(column)
    return ''


def _row_matches_condition(out: pd.DataFrame, row_index: int, condition: str) -> bool:
    condition_key = normalize_key(condition)
    if not condition_key:
        return False
    values = []
    for column in out.columns:
        values.append(clean_cell(out.at[row_index, column]) if row_index in out.index else '')
    row_text = normalize_key(' '.join(values))
    return condition_key in row_text


def _apply_custom_rules(out: pd.DataFrame) -> pd.DataFrame:
    if out is None or out.empty:
        return out

    rules = custom_rules_from_rules(_rules())
    if not rules:
        return out

    for rule in rules:
        if not rule.get('enabled', True):
            continue
        target_column = _target_column_by_rule(out, str(rule.get('target_column', '')))
        if not target_column:
            continue
        condition = str(rule.get('condition', ''))
        fill_value = clean_cell(rule.get('fill_value', ''))
        only_when_empty = bool(rule.get('only_when_empty', True))
        for row_index in out.index:
            if not _row_matches_condition(out, row_index, condition):
                continue
            if only_when_empty and not _is_empty_text(out.at[row_index, target_column]):
                continue
            out.at[row_index, target_column] = fill_value
    return out


def sanitize_for_bling(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()

    out = df.copy().fillna('')
    out.columns = [clean_cell(column) for column in out.columns]

    for col in out.columns:
        if looks_like_gtin_column(col):
            out[col] = out[col].apply(clean_gtin)
        elif _looks_like_image_column(col):
            out[col] = out[col].apply(normalize_image_urls)
        else:
            out[col] = out[col].apply(clean_cell)

    out = _fill_default_measures(out)
    out = _fill_measure_unit(out)
    out = _fill_default_supplier(out)
    out = _apply_custom_rules(out)
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
