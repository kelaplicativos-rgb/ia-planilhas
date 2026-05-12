from __future__ import annotations

import re
from io import BytesIO
from typing import Any

import pandas as pd

from bling_app_zero.core.gtin import clean_gtin, looks_like_gtin_column
from bling_app_zero.core.measurements import normalize_measure_columns, normalize_measures_resource_enabled
from bling_app_zero.core.post_mapping_defaults import apply_post_mapping_defaults
from bling_app_zero.core.text import clean_cell, normalize_key
from bling_app_zero.core.user_rules import custom_rules_from_rules, get_user_rules, measure_defaults_from_rules

IMAGE_COLUMN_TERMS = [
    'imagem', 'imagens', 'image', 'images', 'foto', 'fotos',
    'url imagem', 'url imagens', 'url imagens externas',
]

PRODUCT_CODE_COLUMN_TERMS = [
    'codigo', 'código', 'codigo produto', 'código produto', 'codigo do produto',
    'código do produto', 'cod fornecedor', 'cód fornecedor', 'cod no fornecedor',
    'cód no fornecedor', 'codigo no fornecedor', 'código no fornecedor', 'sku',
    'referencia', 'referência',
]

PRODUCT_NAME_COLUMN_TERMS = ['descricao', 'descrição', 'nome', 'produto', 'titulo', 'título']

EMPTY_RULE_MARKERS = {
    'vazio',
    '#vazio',
    '__vazio__',
    'em branco',
    'embranco',
    'branco',
    'limpar',
    'sem informacao',
    'seminformacao',
}

DEFAULT_MEASURES_CM = {'altura': '2', 'largura': '11', 'profundidade': '18', 'comprimento': '18'}
DEFAULT_SUPPLIER = 'Não definido'
DEFAULT_MEASURE_UNIT = 'UN'
SUPPLIER_INVALID_KEYS = {
    '', 'nan', 'none', 'null', 'na', 'n/a', 'nao informado', 'naoinformado',
    'sem informacao', 'seminformacao', 'indefinido', 'undefined',
}
SUPPLIER_CODE_RE = re.compile(r'^[A-Za-z]{0,6}\d+[A-Za-z0-9._/-]*$')


def _rules() -> dict[str, Any]:
    try:
        return get_user_rules()
    except Exception:
        return {
            'supplier_default': DEFAULT_SUPPLIER,
            'measure_unit_default': DEFAULT_MEASURE_UNIT,
            'height_default': DEFAULT_MEASURES_CM['altura'],
            'width_default': DEFAULT_MEASURES_CM['largura'],
            'depth_default': DEFAULT_MEASURES_CM['profundidade'],
            'length_default': DEFAULT_MEASURES_CM['comprimento'],
            'box_items_default': '1',
            'clean_invalid_gtin': True,
            'normalize_image_separator': True,
            'invalid_gtin_mode': 'limpar',
            'image_separator': '|',
            'auto_product_code': True,
            'unique_product_code': True,
            'custom_rules': [],
        }


def _resource_enabled(key: str, default: bool = True) -> bool:
    return bool(_rules().get(key, default))


def _is_empty_rule_marker(value: object) -> bool:
    return normalize_key(clean_cell(value)) in EMPTY_RULE_MARKERS


def _looks_like_image_column(column: object) -> bool:
    key = normalize_key(column)
    return any(normalize_key(term) in key for term in IMAGE_COLUMN_TERMS)


def _looks_like_product_code_column(column: object) -> bool:
    key = normalize_key(column)
    if not key or looks_like_gtin_column(column):
        return False
    return key in {normalize_key(term) for term in PRODUCT_CODE_COLUMN_TERMS}


def _looks_like_product_name_column(column: object) -> bool:
    key = normalize_key(column)
    return key in {normalize_key(term) for term in PRODUCT_NAME_COLUMN_TERMS}


def _looks_like_supplier_column(column: object) -> bool:
    return normalize_key(column) in {'fornecedor', 'nome fornecedor', 'nome do fornecedor', 'supplier'}


def _looks_like_measure_unit_column(column: object) -> bool:
    return normalize_key(column) in {
        'unidade', 'unidade de medida', 'unidade medida', 'unidade das medidas',
        'unidade dimensoes', 'unidade dimensoes produto',
    }


def _measure_kind(column: object) -> str:
    key = normalize_key(column)
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
    return normalize_key(text) in {'nan', 'none', 'null', 'na', 'n/a', 'nao informado', 'naoinformado', 'sem informacao', 'seminformacao'}


def _is_invalid_supplier_value(value: object) -> bool:
    text = clean_cell(value).strip()
    key = normalize_key(text)
    if key in SUPPLIER_INVALID_KEYS or len(text) <= 2:
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
    return normalize_key(text) in {'sem medida', 'semmedida', '0', '0000'}


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


def _safe_code_text(value: object) -> str:
    text = clean_cell(value)
    text = re.sub(r'\s+', '-', text)
    text = re.sub(r'[^A-Za-z0-9._-]+', '', text)
    text = re.sub(r'-+', '-', text).strip('-._')
    return text[:60]


def _gtin_code_from_row(out: pd.DataFrame, row_index: int) -> str:
    for column in out.columns:
        if looks_like_gtin_column(column):
            value = clean_gtin(out.at[row_index, column]) if row_index in out.index else ''
            if value:
                return value[:60]
    return ''


def _fallback_code_from_row(out: pd.DataFrame, row_index: int) -> str:
    if not _resource_enabled('auto_product_code', True):
        return ''
    gtin_code = _gtin_code_from_row(out, row_index)
    if gtin_code:
        return gtin_code
    for column in [c for c in out.columns if _looks_like_product_name_column(c)]:
        value = clean_cell(out.at[row_index, column]) if row_index in out.index else ''
        key = normalize_key(value)
        if key:
            base = re.sub(r'[^a-z0-9]+', '', key)[:24]
            if base:
                return f'auto-{base}-{row_index + 1}'[:60]
    return f'auto-{row_index + 1}'


def _make_unique_code(base_code: str, row_index: int, seen: set[str]) -> str:
    base = _safe_code_text(base_code)
    if not base and _resource_enabled('auto_product_code', True):
        base = f'auto-{row_index + 1}'
    if not base:
        return ''
    candidate = base[:60]
    if not _resource_enabled('unique_product_code', True):
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
    for column in [c for c in out.columns if _looks_like_product_code_column(c)]:
        seen: set[str] = set()
        values: list[str] = []
        for position, row_index in enumerate(out.index):
            base_code = _safe_code_text(out.at[row_index, column])
            if not base_code:
                base_code = _fallback_code_from_row(out, row_index)
            unique_code = _make_unique_code(base_code, position, seen)
            if unique_code:
                seen.add(normalize_key(unique_code))
            values.append(unique_code)
        out[column] = values
    return out


def _fill_default_measures(out: pd.DataFrame) -> pd.DataFrame:
    defaults = measure_defaults_from_rules(_rules())
    for column in out.columns:
        kind = _measure_kind(column)
        if kind:
            default_value = str(defaults.get(kind, DEFAULT_MEASURES_CM.get(kind, '')) or '')
            out[column] = out[column].apply(lambda value: default_value if _is_empty_measure(value) else clean_cell(value))
    return out


def _fill_default_supplier(out: pd.DataFrame) -> pd.DataFrame:
    supplier_default = str(_rules().get('supplier_default') or DEFAULT_SUPPLIER)
    for column in out.columns:
        if _looks_like_supplier_column(column):
            out[column] = out[column].apply(lambda value: supplier_default if _is_invalid_supplier_value(value) else clean_cell(value))
    return out


def _fill_measure_unit(out: pd.DataFrame) -> pd.DataFrame:
    measure_unit = str(_rules().get('measure_unit_default') or DEFAULT_MEASURE_UNIT)
    for column in out.columns:
        if _looks_like_measure_unit_column(column):
            out[column] = out[column].apply(lambda value: measure_unit if _is_empty_text(value) else clean_cell(value))
    return out


def _target_column_by_rule(out: pd.DataFrame, target_column: str) -> str:
    target_key = normalize_key(target_column)
    for column in out.columns:
        if normalize_key(column) == target_key:
            return str(column)
    return ''


def _apply_custom_rules(out: pd.DataFrame, *, force_empty_only: bool = False) -> pd.DataFrame:
    for rule in custom_rules_from_rules(_rules()):
        if not rule.get('enabled', True):
            continue
        target_column = _target_column_by_rule(out, str(rule.get('target_column', '')))
        if not target_column:
            continue
        fill_value = clean_cell(rule.get('fill_value', ''))
        is_empty_marker = _is_empty_rule_marker(fill_value)
        if force_empty_only and not is_empty_marker:
            continue
        if is_empty_marker:
            out[target_column] = ''
            continue
        if force_empty_only:
            continue
        only_when_empty = bool(rule.get('only_when_empty', False))
        if only_when_empty:
            out[target_column] = out[target_column].apply(lambda value: fill_value if _is_empty_text(value) else clean_cell(value))
        else:
            out[target_column] = fill_value
    return out


def sanitize_for_bling(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()

    out = df.copy().fillna('')
    out.columns = [clean_cell(column) for column in out.columns]

    clean_gtin_enabled = _resource_enabled('clean_invalid_gtin', True)
    normalize_images_enabled = _resource_enabled('normalize_image_separator', True)

    for col in out.columns:
        if looks_like_gtin_column(col) and clean_gtin_enabled:
            out[col] = out[col].apply(clean_gtin)
        elif _looks_like_image_column(col) and normalize_images_enabled:
            out[col] = out[col].apply(normalize_image_urls)
        else:
            out[col] = out[col].apply(clean_cell)

    if normalize_measures_resource_enabled(False):
        out = normalize_measure_columns(out)

    # Regras manuais habilitadas continuam funcionando, mas respeitando only_when_empty quando marcado.
    # Quando o valor da regra for VAZIO, EM BRANCO, LIMPAR ou #VAZIO, a coluna é limpa de verdade.
    out = _apply_custom_rules(out)

    # BLINGFIX: padrões finais pós-mapeamento.
    # Só preenche colunas existentes e vazias. Nunca sobrescreve valor mapeado/manual.
    out = apply_post_mapping_defaults(out, _rules())

    # Garante que o comando VAZIO vença qualquer padrão final aplicado depois.
    out = _apply_custom_rules(out, force_empty_only=True)

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
