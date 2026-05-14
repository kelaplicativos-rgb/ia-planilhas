from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.core.final_download_resources import (
    clean_cells_resource,
    clean_invalid_gtin_resource,
    normalize_image_separator_resource,
    normalize_image_urls,
    normalize_stock_status_resource,
    unique_product_codes_resource,
)
from bling_app_zero.core.measurements import normalize_measure_columns, normalize_measures_resource_enabled
from bling_app_zero.core.post_mapping_defaults import apply_post_mapping_defaults
from bling_app_zero.core.rule_value_validator import is_empty_rule_command
from bling_app_zero.core.text import clean_cell, normalize_key
from bling_app_zero.core.user_rules import custom_rules_from_rules, get_user_rules, stock_defaults_from_rules
from bling_app_zero.features.contracts import FeatureContext, FeatureDefinition, FeatureResult

RESPONSIBLE_FILE = 'bling_app_zero/features/download_pipeline.py'
DEFAULT_SUPPLIER = 'Não definido'
DEFAULT_MEASURE_UNIT = 'UN'
DEFAULT_MEASURES_CM = {'altura': '2', 'largura': '11', 'profundidade': '18', 'comprimento': '18'}


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
            'stock_available_default': '1000',
            'stock_low_default': '0',
            'stock_out_default': '0',
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


def _target_column_by_rule(out: pd.DataFrame, target_column: str) -> str:
    target_key = normalize_key(target_column)
    for column in out.columns:
        if normalize_key(column) == target_key:
            return str(column)
    return ''


def _is_empty_rule_marker(value: object) -> bool:
    return is_empty_rule_command(clean_cell(value))


def _is_empty_text(value: object) -> bool:
    text = clean_cell(value).strip()
    if not text:
        return True
    return normalize_key(text) in {'nan', 'none', 'null', 'na', 'n/a', 'nao informado', 'naoinformado', 'sem informacao', 'seminformacao'}


def run_clean_cells(context: FeatureContext) -> FeatureResult:
    result = clean_cells_resource(_df_from_context(context))
    return _with_final(context, result.df, result.message)


def run_clean_invalid_gtin(context: FeatureContext) -> FeatureResult:
    result = clean_invalid_gtin_resource(_df_from_context(context), enabled=_resource_enabled('clean_invalid_gtin', True))
    return _with_final(context, result.df, result.message)


def run_normalize_image_separator(context: FeatureContext) -> FeatureResult:
    result = normalize_image_separator_resource(_df_from_context(context), enabled=_resource_enabled('normalize_image_separator', True))
    return _with_final(context, result.df, result.message)


def run_normalize_stock_status(context: FeatureContext) -> FeatureResult:
    result = normalize_stock_status_resource(_df_from_context(context), defaults=stock_defaults_from_rules(_rules()))
    return _with_final(context, result.df, result.message)


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
    rules = _rules()
    result = unique_product_codes_resource(
        _df_from_context(context),
        auto_product_code=bool(rules.get('auto_product_code', True)),
        unique_product_code=bool(rules.get('unique_product_code', True)),
    )
    return _with_final(context, result.df, result.message)


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
NORMALIZE_STOCK_STATUS_FEATURE = FeatureDefinition(
    key='normalize_stock_status',
    title='Converter status de estoque',
    description='Converte Disponível/Baixo/Esgotado em quantidade usando os padrões definidos pelo usuário.',
    scope='estoque',
    stage='download',
    status='stable',
    state_key='feature_normalize_stock_status_enabled',
    provides=('status_estoque_convertido',),
    owner_file=RESPONSIBLE_FILE,
    runner=run_normalize_stock_status,
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
    NORMALIZE_STOCK_STATUS_FEATURE,
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
    'NORMALIZE_STOCK_STATUS_FEATURE',
    'POST_MAPPING_DEFAULTS_FEATURE',
    'UNIQUE_PRODUCT_CODES_FEATURE',
    'normalize_image_urls',
    'run_clean_cells',
    'run_clean_invalid_gtin',
    'run_custom_rules',
    'run_empty_custom_rules',
    'run_normalize_image_separator',
    'run_normalize_measures',
    'run_normalize_stock_status',
    'run_post_mapping_defaults',
    'run_unique_product_codes',
]
