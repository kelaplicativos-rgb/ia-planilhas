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
from bling_app_zero.core.user_rules import get_user_rules, stock_defaults_from_rules
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
    UNIQUE_PRODUCT_CODES_FEATURE,
)

__all__ = [
    'CLEAN_CELLS_FEATURE',
    'CLEAN_INVALID_GTIN_FEATURE',
    'DOWNLOAD_FEATURES',
    'NORMALIZE_IMAGE_SEPARATOR_FEATURE',
    'NORMALIZE_MEASURES_FEATURE',
    'NORMALIZE_STOCK_STATUS_FEATURE',
    'UNIQUE_PRODUCT_CODES_FEATURE',
    'normalize_image_urls',
    'run_clean_cells',
    'run_clean_invalid_gtin',
    'run_normalize_image_separator',
    'run_normalize_measures',
    'run_normalize_stock_status',
    'run_unique_product_codes',
]
