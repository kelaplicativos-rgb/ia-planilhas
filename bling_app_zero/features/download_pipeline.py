from __future__ import annotations

import pandas as pd

from bling_app_zero.core.final_download_resources import normalize_image_urls
from bling_app_zero.features.contracts import FeatureContext, FeatureDefinition, FeatureResult

RESPONSIBLE_FILE = 'bling_app_zero/features/download_pipeline.py'


def _df_from_context(context: FeatureContext) -> pd.DataFrame:
    if isinstance(context.final_df, pd.DataFrame):
        return context.final_df.copy().fillna('')
    if isinstance(context.source_df, pd.DataFrame):
        return context.source_df.copy().fillna('')
    return pd.DataFrame()


def _passthrough(context: FeatureContext, message: str) -> FeatureResult:
    return FeatureResult(ok=True, message=message, final_df=_df_from_context(context))


def run_clean_cells(context: FeatureContext) -> FeatureResult:
    return _passthrough(context, 'Sem alteração automática: o modelo anexado é o contrato da saída.')


def run_clean_invalid_gtin(context: FeatureContext) -> FeatureResult:
    return _passthrough(context, 'GTIN mantido como veio do mapeamento.')


def run_normalize_image_separator(context: FeatureContext) -> FeatureResult:
    return _passthrough(context, 'Imagens mantidas como vieram do mapeamento.')


def run_normalize_stock_status(context: FeatureContext) -> FeatureResult:
    return _passthrough(context, 'Status/quantidade mantidos como vieram do mapeamento.')


def run_normalize_measures(context: FeatureContext) -> FeatureResult:
    return _passthrough(context, 'Medidas mantidas como vieram do mapeamento.')


def run_unique_product_codes(context: FeatureContext) -> FeatureResult:
    return _passthrough(context, 'Códigos mantidos como vieram do mapeamento.')


CLEAN_CELLS_FEATURE = FeatureDefinition(
    key='clean_cells',
    title='Manter modelo mapeado',
    description='Não altera automaticamente o resultado final; o layout anexado é o contrato.',
    scope='global',
    stage='download',
    status='stable',
    state_key='feature_clean_cells_enabled',
    provides=('modelo_mapeado_preservado',),
    owner_file=RESPONSIBLE_FILE,
    runner=run_clean_cells,
)
CLEAN_INVALID_GTIN_FEATURE = FeatureDefinition(
    key='clean_invalid_gtin',
    title='Manter GTIN mapeado',
    description='Não altera GTIN automaticamente no download universal.',
    scope='global',
    stage='download',
    status='stable',
    state_key='clean_invalid_gtin',
    provides=('gtin_preservado',),
    owner_file=RESPONSIBLE_FILE,
    runner=run_clean_invalid_gtin,
)
NORMALIZE_IMAGE_SEPARATOR_FEATURE = FeatureDefinition(
    key='normalize_image_separator',
    title='Manter imagens mapeadas',
    description='Não altera separadores de imagem automaticamente no download universal.',
    scope='global',
    stage='download',
    status='stable',
    state_key='normalize_image_separator',
    provides=('imagens_preservadas',),
    owner_file=RESPONSIBLE_FILE,
    runner=run_normalize_image_separator,
)
NORMALIZE_STOCK_STATUS_FEATURE = FeatureDefinition(
    key='normalize_stock_status',
    title='Manter estoque mapeado',
    description='Não converte status de estoque automaticamente no download universal.',
    scope='global',
    stage='download',
    status='stable',
    state_key='feature_normalize_stock_status_enabled',
    provides=('estoque_preservado',),
    owner_file=RESPONSIBLE_FILE,
    runner=run_normalize_stock_status,
)
NORMALIZE_MEASURES_FEATURE = FeatureDefinition(
    key='normalize_measures_to_meters',
    title='Manter medidas mapeadas',
    description='Não converte medidas automaticamente no download universal.',
    scope='global',
    stage='download',
    status='stable',
    state_key='normalize_measures_to_meters',
    provides=('medidas_preservadas',),
    owner_file=RESPONSIBLE_FILE,
    runner=run_normalize_measures,
)
UNIQUE_PRODUCT_CODES_FEATURE = FeatureDefinition(
    key='unique_product_codes',
    title='Manter códigos mapeados',
    description='Não gera ou altera códigos automaticamente no download universal.',
    scope='global',
    stage='download',
    status='stable',
    state_key='unique_product_code',
    provides=('codigos_preservados',),
    owner_file=RESPONSIBLE_FILE,
    runner=run_unique_product_codes,
)

DOWNLOAD_FEATURES = ()

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
