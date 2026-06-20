from __future__ import annotations

from bling_app_zero.features_runtime.contracts import FeatureContract

STEP_MODELO = 'modelo'
STEP_ORIGEM = 'origem'
STEP_ENTRADA = 'entrada'
STEP_OPERACAO = 'operacao'
STEP_PRECIFICACAO = 'precificacao'
STEP_CATEGORIZACAO = 'categorizacao'
STEP_MAPEAMENTO = 'mapeamento'
STEP_REGRAS = 'regras'
STEP_IA = 'ia'
STEP_PREVIEW = 'preview'
STEP_DOWNLOAD = 'download'

OP_UNIVERSAL = 'universal'
OP_API_PENDING = 'api_pending'
OP_API_CADASTRO = 'api_cadastro'
OP_API_ESTOQUE = 'api_estoque'
OP_API_ATUALIZACAO_PRECO = 'api_atualizacao_preco'
API_OPERATIONS = {OP_API_PENDING, OP_API_CADASTRO, OP_API_ESTOQUE, OP_API_ATUALIZACAO_PRECO}

API_STEPS = (STEP_ORIGEM, STEP_ENTRADA, STEP_OPERACAO, STEP_DOWNLOAD)

# Ordem oficial source-first:
# origem/dados alimentam a base; só depois o usuário escolhe a operação real.
UNIVERSAL_STEPS = (
    STEP_MODELO,
    STEP_ORIGEM,
    STEP_ENTRADA,
    STEP_OPERACAO,
    STEP_PRECIFICACAO,
    STEP_CATEGORIZACAO,
    STEP_MAPEAMENTO,
    STEP_REGRAS,
    STEP_IA,
    STEP_PREVIEW,
    STEP_DOWNLOAD,
)
CSV_PRODUCT_STEPS = UNIVERSAL_STEPS
CSV_STOCK_STEPS = UNIVERSAL_STEPS
CSV_PRICE_STEPS = UNIVERSAL_STEPS

CSV_CONTRACT = FeatureContract('universal_mapping_csv', 'Modelo para mapear', OP_UNIVERSAL, 'csv', False, True, True, True, True, True, True, 'Download Modelo Mapeado', UNIVERSAL_STEPS)
API_PENDING_CONTRACT = FeatureContract(OP_API_PENDING, 'Escolher operação API', OP_API_PENDING, 'api', True, False, False, False, False, False, False, 'Escolher operação', API_STEPS)
API_CADASTRO_CONTRACT = FeatureContract(OP_API_CADASTRO, 'API Cadastro de Produtos', OP_API_CADASTRO, 'api', True, False, False, False, False, False, False, 'Enviar cadastro', API_STEPS)
API_ESTOQUE_CONTRACT = FeatureContract(OP_API_ESTOQUE, 'API Estoque por Depósito', OP_API_ESTOQUE, 'api', True, False, False, False, False, False, False, 'Enviar estoque', API_STEPS)
API_PRECO_CONTRACT = FeatureContract(OP_API_ATUALIZACAO_PRECO, 'API Atualização de Preços', OP_API_ATUALIZACAO_PRECO, 'api', True, False, False, False, False, False, False, 'Enviar preços', API_STEPS)
API_CONTRACT = API_PENDING_CONTRACT
CONTRACTS = {
    (OP_UNIVERSAL, 'csv'): CSV_CONTRACT,
    (OP_API_PENDING, 'api'): API_PENDING_CONTRACT,
    (OP_API_CADASTRO, 'api'): API_CADASTRO_CONTRACT,
    (OP_API_ESTOQUE, 'api'): API_ESTOQUE_CONTRACT,
    (OP_API_ATUALIZACAO_PRECO, 'api'): API_PRECO_CONTRACT,
}
OPERATION_ALIASES = {'': OP_UNIVERSAL, OP_UNIVERSAL: OP_UNIVERSAL, 'api': OP_API_PENDING, OP_API_PENDING: OP_API_PENDING, 'cadastro': OP_API_CADASTRO, 'estoque': OP_API_ESTOQUE, 'atualizacao_preco': OP_API_ATUALIZACAO_PRECO}
MODE_ALIASES = {'api_direct': 'api', 'api': 'api', 'download': 'csv', 'csv': 'csv', 'planilha': 'csv', 'universal': 'csv', '': 'csv'}


def normalize_operation(value: object) -> str:
    raw = str(value or '').strip().lower()
    return OPERATION_ALIASES.get(raw, OP_API_PENDING if raw.startswith('api_') else OP_UNIVERSAL)


def normalize_mode(value: object) -> str:
    return MODE_ALIASES.get(str(value or '').strip().lower(), 'csv')


def get_feature_contract(operation: object, mode: object) -> FeatureContract:
    normalized_mode = normalize_mode(mode)
    if normalized_mode == 'api':
        op = normalize_operation(operation)
        if op not in API_OPERATIONS:
            op = OP_API_PENDING
        return CONTRACTS.get((op, 'api'), API_PENDING_CONTRACT)
    return CSV_CONTRACT


def list_feature_contracts() -> list[FeatureContract]:
    return [CSV_CONTRACT, API_PENDING_CONTRACT, API_CADASTRO_CONTRACT, API_ESTOQUE_CONTRACT, API_PRECO_CONTRACT]


__all__ = [
    'API_STEPS', 'CSV_PRICE_STEPS', 'CSV_PRODUCT_STEPS', 'CSV_STOCK_STEPS',
    'CONTRACTS', 'MODE_ALIASES', 'OPERATION_ALIASES', 'STEP_CATEGORIZACAO', 'STEP_DOWNLOAD',
    'STEP_ENTRADA', 'STEP_IA', 'STEP_MAPEAMENTO', 'STEP_MODELO', 'STEP_OPERACAO', 'STEP_ORIGEM',
    'STEP_PRECIFICACAO', 'STEP_PREVIEW', 'STEP_REGRAS', 'UNIVERSAL_STEPS',
    'get_feature_contract', 'list_feature_contracts', 'normalize_mode', 'normalize_operation',
]
