from __future__ import annotations

from bling_app_zero.features_runtime.contracts import FeatureContract

STEP_MODELO = 'modelo'
STEP_ORIGEM = 'origem'
STEP_ENTRADA = 'entrada'
STEP_PRECIFICACAO = 'precificacao'
STEP_MAPEAMENTO = 'mapeamento'
STEP_REGRAS = 'regras'
STEP_PREVIEW = 'preview'
STEP_DOWNLOAD = 'download'

API_STEPS = (STEP_ORIGEM, STEP_ENTRADA, STEP_DOWNLOAD)
UNIVERSAL_STEPS = (STEP_MODELO, STEP_ORIGEM, STEP_ENTRADA, STEP_PRECIFICACAO, STEP_MAPEAMENTO, STEP_REGRAS, STEP_PREVIEW, STEP_DOWNLOAD)
CSV_PRODUCT_STEPS = UNIVERSAL_STEPS
CSV_STOCK_STEPS = UNIVERSAL_STEPS
CSV_PRICE_STEPS = UNIVERSAL_STEPS

CSV_CONTRACT = FeatureContract('universal_mapping_csv', 'Modelo para mapear', 'universal', 'csv', False, True, True, True, True, True, True, 'Download Modelo Mapeado', UNIVERSAL_STEPS)
API_CONTRACT = FeatureContract('api_compat', 'Enviar', 'universal', 'api', True, False, False, False, False, False, False, 'Enviar', API_STEPS)
CONTRACTS = {('universal', 'csv'): CSV_CONTRACT, ('universal', 'api'): API_CONTRACT}
OPERATION_ALIASES = {'': 'universal'}
MODE_ALIASES = {'api_direct': 'api', 'api': 'api', 'download': 'csv', 'csv': 'csv', 'planilha': 'csv', 'universal': 'csv', '': 'csv'}


def normalize_operation(value: object) -> str:
    return 'universal'


def normalize_mode(value: object) -> str:
    return MODE_ALIASES.get(str(value or '').strip().lower(), 'csv')


def get_feature_contract(operation: object, mode: object) -> FeatureContract:
    return API_CONTRACT if normalize_mode(mode) == 'api' else CSV_CONTRACT


def list_feature_contracts() -> list[FeatureContract]:
    return [CSV_CONTRACT, API_CONTRACT]


__all__ = [
    'API_STEPS', 'CSV_PRICE_STEPS', 'CSV_PRODUCT_STEPS', 'CSV_STOCK_STEPS',
    'CONTRACTS', 'MODE_ALIASES', 'OPERATION_ALIASES', 'STEP_DOWNLOAD',
    'STEP_ENTRADA', 'STEP_MAPEAMENTO', 'STEP_MODELO', 'STEP_ORIGEM',
    'STEP_PRECIFICACAO', 'STEP_PREVIEW', 'STEP_REGRAS', 'UNIVERSAL_STEPS',
    'get_feature_contract', 'list_feature_contracts', 'normalize_mode', 'normalize_operation',
]
