from __future__ import annotations

import re
from typing import Any

import pandas as pd

from bling_app_zero.core.gtin import clean_gtin, looks_like_gtin_column
from bling_app_zero.core.measurements import normalize_measure_columns, normalize_measures_resource_enabled
from bling_app_zero.core.post_mapping_defaults import apply_post_mapping_defaults
from bling_app_zero.core.rule_value_validator import is_empty_rule_command
from bling_app_zero.core.text import clean_cell, normalize_key
from bling_app_zero.core.user_rules import custom_rules_from_rules, get_user_rules
from bling_app_zero.features.contracts import FeatureContext, FeatureDefinition, FeatureResult

RESPONSIBLE_FILE = 'bling_app_zero/features/download_pipeline.py'

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
DEFAULT_SUPPLIER = 'Não definido'
DEFAULT_MEASURE_UNIT = 'UN'
DEFAULT_MEASURES_CM = {'altura': '2', 'largura': '11', 'profundidade': '18', 'comprimento': '18'}
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


def _df_from_context(context: FeatureContext) -> pd.DataFrame:
    if isinstance(context.final_df, pd.DataFrame):
        return context.final_df.copy().fillna('')
    if isinstance(context.source_df, pd.DataFrame):
        return context.source_df.copy().fillna('')
    return pd.DataFrame()


def _with_final(context: FeatureContext, df: pd.DataFrame, message: str) -> FeatureResult:
    return FeatureResult(ok=True, message=message, final_df=df.copy().fillna(''))


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


def _is_empty_text(value: object) -> bool:
    text = clean_cell(value).strip()
    if not text:
        return True
    return normalize_key(text) in {'nan', 'none', 'null', 'na', 'n/a', 'nao informado', 'naoinformado', 'sem informacao', 'seminformacao'}


def _is_empty_rule_marker(value: object) -> bool:
    return is_empty_rule_command(clean_cell(value))


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


def _target_column_by_rule(out: pd.DataFrame, target_column: str) -> str:
    target_key = normalize_key(target_column)
    for column in out.columns:
        if normalize_key(column) == target_key:
            return str(column)
    return ''


def run_clean_cells(context: FeatureContext) -> FeatureResult:
    df = _df_from_context(context)
    if df.empty:
        return _with_final(context, df, 'Sem dados para limpeza textual.')
    out = df.copy().fillna('')
    out.columns = [clean_cell(column) for column in out.columns]
    for column in out.columns:
        out[column] = out[column].apply(clean_cell)
    return _with_final(context, out, 'Células e nomes de colunas limpos.')


def run_clean_invalid_gtin(context: FeatureContext) -> FeatureResult:
    df = _df_from_context(context)
    if df.empty or not _resource_enabled('clean_invalid_gtin', True):
        return _with_final(context, df, 'Limpeza de GTIN desativada ou sem dados.')
    out = df.copy().fillna('')
    changed = 0
    for column in out.columns:
        if looks_like_gtin_column(column):
            before = out[column].astype(str).tolist()
            out[column] = out[column].apply(clean_gtin)
            changed += sum(1 for old, new in zip(before, out[column].astype(str).tolist()) if old != new)
    return _with_final(context, out, f'GTIN limpo em {changed} célula(s).')


def run_normalize_image_separator(context: FeatureContext) -> FeatureResult:
    df = _df_from_context(context)
    if df.empty or not _resource_enabled('normalize_image_separator', True):
        return _with_final(context, df, 'Normalização de imagens desativada ou sem dados.')
    out = df.copy().fillna('')
    columns = [column for column in out.columns if _looks_like_image_column(column)]
    for column in columns:
        out[column] = out[column].apply(normalize_image_urls)
    return _with_final(context, out, f'Imagens normalizadas em {len(columns)} coluna(s).')


def run_normalize_measures(context: FeatureContext) -> FeatureResult:
    df = _df_from_context(context)
    if df.empty or not normalize_measures_resource_enabled(False):
        return _with_final(context, df, 'Normalização de medidas desativada ou sem dados.')
    out = normalize_measure_columns(df.copy().fillna(''))
    return _with_final(context, out, 'Medidas normalizadas para metros.')


def run_custom_rules(context: FeatureContext) -> FeatureResult:
    df = _df_from_context(context)
    if df.empty:
        return _with_final(context, df, 'Sem dados para regras personalizadas.')
    out = df.copy().fillna('')
    for rule in custom_rules_from_rules(_rules()):
        if not rule.get('enabled', True):
            continue
        target_column = _target_column_by_rule(out, str(rule.get('target_column', '')))
        if not target_column:
            continue
        fill_value = clean_cell(rule.get('fill_value', ''))
        is_empty_marker = _is_empty_rule_marker(fill_value)
        if is_empty_marker:
            out[target_column] = ''
            continue
        only_when_empty = bool(rule.get('only_when_empty', False))
        if only_when_empty:
            out[target_column] = out[target_column].apply(lambda value: fill_value if _is_empty_text(value) else clean_cell(value))
        else:
            out[target_column] = fill_value
    return _with_final(context, out, 'Regras personalizadas aplicadas.')


def run_post_mapping_defaults(context: FeatureContext) -> FeatureResult:
    df = _df_from_context(context)
    if df.empty:
        return _with_final(context, df, 'Sem dados para defaults pós-mapeamento.')
    out = apply_post_mapping_defaults(df.copy().fillna(''), _rules())
    return _with_final(context, out, 'Defaults pós-mapeamento aplicados.')


def run_empty_custom_rules(context: FeatureContext) -> FeatureResult:
    df = _df_from_context(context)
    if df.empty:
        return _with_final(context, df, 'Sem dados para regras de esvaziamento.')
    out = df.copy().fillna('')
    for rule in custom_rules_from_rules(_rules()):
        if not rule.get('enabled', True):
            continue
        target_column = _target_column_by_rule(out, str(rule.get('target_column', '')))
        if not target_column:
            continue
        fill_value = clean_cell(rule.get('fill_value', ''))
        if _is_empty_rule_marker(fill_value):
            out[target_column] = ''
    return _with_final(context, out, 'Regras de esvaziamento aplicadas.')


def run_unique_product_codes(context: FeatureContext) -> FeatureResult:
    df = _df_from_context(context)
    if df.empty:
        return _with_final(context, df, 'Sem dados para código automático.')
    out = df.copy().fillna('')
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
    return _with_final(context, out, 'Códigos de produto normalizados e deduplicados.')


CLEAN_CELLS_FEATURE = FeatureDefinition(
    key='clean_cells',
    title='Limpar textos e colunas',
    description='Remove sujeira textual básica das células e nomes de colunas antes do CSV.',
    scope='global',
    stage='download',
    status='stable',
    state_key='feature_clean_cells_enabled',
    provides=('textos_limpos',),
    owner_file=RESPONSIBLE_FILE,
    runner=run_clean_cells,
)
CLEAN_INVALID_GTIN_FEATURE = FeatureDefinition(
    key='clean_invalid_gtin',
    title='Limpar GTIN inválido',
    description='Remove GTIN/EAN fora dos tamanhos aceitos antes do CSV final.',
    scope='global',
    stage='download',
    status='stable',
    state_key='clean_invalid_gtin',
    provides=('gtin_sanitizado',),
    owner_file=RESPONSIBLE_FILE,
    runner=run_clean_invalid_gtin,
)
NORMALIZE_IMAGE_SEPARATOR_FEATURE = FeatureDefinition(
    key='normalize_image_separator',
    title='Separar imagens por |',
    description='Garante que múltiplas URLs de imagens saiam separadas por barra vertical no CSV.',
    scope='cadastro',
    stage='download',
    status='stable',
    state_key='normalize_image_separator',
    provides=('imagens_normalizadas',),
    owner_file=RESPONSIBLE_FILE,
    runner=run_normalize_image_separator,
)
NORMALIZE_MEASURES_FEATURE = FeatureDefinition(
    key='normalize_measures_to_meters',
    title='Normalizar medidas para metro',
    description='Converte medidas como altura, largura e comprimento para o padrão esperado pelo Bling.',
    scope='cadastro',
    stage='download',
    status='beta',
    state_key='normalize_measures_to_meters',
    provides=('medidas_normalizadas',),
    owner_file=RESPONSIBLE_FILE,
    runner=run_normalize_measures,
)
CUSTOM_RULES_FEATURE = FeatureDefinition(
    key='custom_rules',
    title='Aplicar regras personalizadas',
    description='Aplica padrões definidos pelo usuário antes dos defaults automáticos.',
    scope='global',
    stage='download',
    status='stable',
    state_key='feature_custom_rules_enabled',
    provides=('regras_personalizadas_aplicadas',),
    owner_file=RESPONSIBLE_FILE,
    runner=run_custom_rules,
)
POST_MAPPING_DEFAULTS_FEATURE = FeatureDefinition(
    key='post_mapping_defaults',
    title='Aplicar defaults pós-mapeamento',
    description='Preenche fornecedor, unidade, medidas e outros defaults após o mapeamento.',
    scope='global',
    stage='download',
    status='stable',
    state_key='feature_post_mapping_defaults_enabled',
    provides=('defaults_pos_mapeamento',),
    owner_file=RESPONSIBLE_FILE,
    runner=run_post_mapping_defaults,
)
EMPTY_CUSTOM_RULES_FEATURE = FeatureDefinition(
    key='empty_custom_rules',
    title='Aplicar regras de campo vazio',
    description='Executa regras que limpam campos depois dos defaults automáticos.',
    scope='global',
    stage='download',
    status='stable',
    state_key='feature_empty_custom_rules_enabled',
    provides=('campos_esvaziados_por_regra',),
    owner_file=RESPONSIBLE_FILE,
    runner=run_empty_custom_rules,
)
UNIQUE_PRODUCT_CODES_FEATURE = FeatureDefinition(
    key='unique_product_codes',
    title='Código automático e único',
    description='Garante código de produto preenchido e sem duplicidade quando o recurso estiver ativo.',
    scope='cadastro',
    stage='download',
    status='stable',
    state_key='unique_product_code',
    provides=('codigos_produto_unicos',),
    owner_file=RESPONSIBLE_FILE,
    runner=run_unique_product_codes,
)

DOWNLOAD_FEATURES = (
    CLEAN_CELLS_FEATURE,
    CLEAN_INVALID_GTIN_FEATURE,
    NORMALIZE_IMAGE_SEPARATOR_FEATURE,
    NORMALIZE_MEASURES_FEATURE,
    CUSTOM_RULES_FEATURE,
    POST_MAPPING_DEFAULTS_FEATURE,
    EMPTY_CUSTOM_RULES_FEATURE,
    UNIQUE_PRODUCT_CODES_FEATURE,
)

__all__ = [
    'CLEAN_CELLS_FEATURE',
    'CLEAN_INVALID_GTIN_FEATURE',
    'CUSTOM_RULES_FEATURE',
    'DOWNLOAD_FEATURES',
    'EMPTY_CUSTOM_RULES_FEATURE',
    'NORMALIZE_IMAGE_SEPARATOR_FEATURE',
    'NORMALIZE_MEASURES_FEATURE',
    'POST_MAPPING_DEFAULTS_FEATURE',
    'UNIQUE_PRODUCT_CODES_FEATURE',
    'normalize_image_urls',
    'run_clean_cells',
    'run_clean_invalid_gtin',
    'run_custom_rules',
    'run_empty_custom_rules',
    'run_normalize_image_separator',
    'run_normalize_measures',
    'run_post_mapping_defaults',
    'run_unique_product_codes',
]
