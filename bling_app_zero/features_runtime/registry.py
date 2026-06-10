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

# BLINGARCH 2026-06-10:
# O fluxo principal passa a tratar Origem como recurso comum. Primeiro o usuário
# decide como finaliza, depois escolhe/carrega a origem, e só então confirma a
# operação/modelo/contrato. Isso permite aproveitar a mesma busca por site para
# cadastro, estoque e atualização de preço.
API_STEPS = (STEP_ORIGEM, STEP_ENTRADA, STEP_DOWNLOAD)
CSV_PRODUCT_STEPS = (STEP_ORIGEM, STEP_ENTRADA, STEP_MODELO, STEP_PRECIFICACAO, STEP_MAPEAMENTO, STEP_REGRAS, STEP_PREVIEW, STEP_DOWNLOAD)
CSV_STOCK_STEPS = (STEP_ORIGEM, STEP_ENTRADA, STEP_MODELO, STEP_MAPEAMENTO, STEP_PREVIEW, STEP_DOWNLOAD)
CSV_PRICE_STEPS = (STEP_ORIGEM, STEP_ENTRADA, STEP_MODELO, STEP_PRECIFICACAO, STEP_MAPEAMENTO, STEP_PREVIEW, STEP_DOWNLOAD)
UNIVERSAL_STEPS = CSV_PRODUCT_STEPS

CONTRACTS: dict[tuple[str, str], FeatureContract] = {
    ('cadastro', 'api'): FeatureContract(
        key='cadastro_api',
        label='Cadastro de produtos via API Bling',
        operation='cadastro',
        mode='api',
        supports_api=True,
        supports_csv=False,
        needs_model=False,
        needs_pricing=True,
        needs_mapping=False,
        needs_rules_review=False,
        needs_download=False,
        primary_action_label='Cadastrar produtos no Bling',
        steps=API_STEPS,
        required_columns=('nome',),
        optional_columns=('codigo', 'preco', 'descricao', 'gtin', 'marca', 'ncm', 'categoria', 'imagens'),
    ),
    ('estoque', 'api'): FeatureContract(
        key='estoque_api',
        label='Atualização de estoque via API Bling',
        operation='estoque',
        mode='api',
        supports_api=True,
        supports_csv=False,
        needs_model=False,
        needs_pricing=False,
        needs_mapping=False,
        needs_rules_review=False,
        needs_download=False,
        primary_action_label='Atualizar estoque no Bling',
        steps=API_STEPS,
        required_columns=('Quantidade',),
        optional_columns=('Código', 'GTIN', 'Depósito'),
    ),
    ('atualizacao_preco', 'api'): FeatureContract(
        key='preco_api',
        label='Atualização de preços via API Bling',
        operation='atualizacao_preco',
        mode='api',
        supports_api=True,
        supports_csv=False,
        needs_model=False,
        needs_pricing=True,
        needs_mapping=False,
        needs_rules_review=False,
        needs_download=False,
        primary_action_label='Atualizar preços no Bling',
        steps=API_STEPS,
        required_columns=('preco',),
        optional_columns=('id', 'codigo', 'gtin'),
    ),
    ('cadastro', 'csv'): FeatureContract(
        key='cadastro_csv',
        label='Cadastro de produtos por planilha',
        operation='cadastro',
        mode='csv',
        supports_api=False,
        supports_csv=True,
        needs_model=True,
        needs_pricing=True,
        needs_mapping=True,
        needs_rules_review=True,
        needs_download=True,
        primary_action_label='Baixar CSV de cadastro',
        steps=CSV_PRODUCT_STEPS,
    ),
    ('estoque', 'csv'): FeatureContract(
        key='estoque_csv',
        label='Atualização de estoque por planilha',
        operation='estoque',
        mode='csv',
        supports_api=False,
        supports_csv=True,
        needs_model=True,
        needs_pricing=False,
        needs_mapping=True,
        needs_rules_review=False,
        needs_download=True,
        primary_action_label='Baixar CSV de estoque',
        steps=CSV_STOCK_STEPS,
    ),
    ('atualizacao_preco', 'csv'): FeatureContract(
        key='preco_csv',
        label='Atualização de preços por planilha',
        operation='atualizacao_preco',
        mode='csv',
        supports_csv=True,
        supports_api=False,
        needs_model=True,
        needs_pricing=True,
        needs_mapping=True,
        needs_rules_review=False,
        needs_download=True,
        primary_action_label='Baixar CSV de preços',
        steps=CSV_PRICE_STEPS,
    ),
    ('universal', 'csv'): FeatureContract(
        key='universal_csv',
        label='Modelo universal por planilha',
        operation='universal',
        mode='csv',
        supports_api=False,
        supports_csv=True,
        needs_model=True,
        needs_pricing=True,
        needs_mapping=True,
        needs_rules_review=True,
        needs_download=True,
        primary_action_label='Baixar arquivo final',
        steps=UNIVERSAL_STEPS,
    ),
}

OPERATION_ALIASES = {
    '': 'universal',
    'modelo': 'universal',
    'modelo final': 'universal',
    'modelo_final': 'universal',
    'modelo_destino': 'universal',
    'planilha': 'universal',
    'csv': 'universal',
    'universal': 'universal',
    'wizard_cadastro_estoque': 'universal',

    'cadastro': 'cadastro',
    'cadastrar': 'cadastro',
    'produto': 'cadastro',
    'produtos': 'cadastro',
    'new_product': 'cadastro',
    'create_product': 'cadastro',
    'cadastro_produto': 'cadastro',
    'cadastro_produtos': 'cadastro',
    'cadastro de produto': 'cadastro',
    'cadastro de produtos': 'cadastro',

    'estoque': 'estoque',
    'stock': 'estoque',
    'saldo': 'estoque',
    'saldos': 'estoque',
    'quantidade': 'estoque',
    'quantidades': 'estoque',
    'atualizacao_estoque': 'estoque',
    'atualização_estoque': 'estoque',
    'atualizar_estoque': 'estoque',
    'atualizar estoque': 'estoque',
    'atualização de estoque': 'estoque',
    'atualizacao de estoque': 'estoque',

    'atualizacao_preco': 'atualizacao_preco',
    'atualizacao_precos': 'atualizacao_preco',
    'atualização_preço': 'atualizacao_preco',
    'atualização_preços': 'atualizacao_preco',
    'atualização_precos': 'atualizacao_preco',
    'atualizar_preco': 'atualizacao_preco',
    'atualizar_precos': 'atualizacao_preco',
    'atualizar preço': 'atualizacao_preco',
    'atualizar preços': 'atualizacao_preco',
    'atualizacao de preco': 'atualizacao_preco',
    'atualizacao de precos': 'atualizacao_preco',
    'atualização de preço': 'atualizacao_preco',
    'atualização de preços': 'atualizacao_preco',
    'preco': 'atualizacao_preco',
    'preço': 'atualizacao_preco',
    'precos': 'atualizacao_preco',
    'preços': 'atualizacao_preco',
    'price': 'atualizacao_preco',
    'prices': 'atualizacao_preco',
}

MODE_ALIASES = {
    'api_direct': 'api',
    'api': 'api',
    'bling': 'api',
    'bling_api': 'api',
    'api_bling': 'api',
    'csv_download': 'csv',
    'download': 'csv',
    'csv': 'csv',
    'planilha': 'csv',
    'universal': 'csv',
    '': 'csv',
}


def normalize_operation(value: object) -> str:
    text = str(value or '').strip().lower()
    if text in {'cadastro', 'estoque', 'atualizacao_preco', 'universal'}:
        return text
    return OPERATION_ALIASES.get(text, 'universal')


def normalize_mode(value: object) -> str:
    text = str(value or '').strip().lower()
    return MODE_ALIASES.get(text, 'csv')


def get_feature_contract(operation: object, mode: object) -> FeatureContract:
    op = normalize_operation(operation)
    md = normalize_mode(mode)
    if (op, md) in CONTRACTS:
        return CONTRACTS[(op, md)]
    if md == 'api' and ('cadastro', 'api') in CONTRACTS:
        return CONTRACTS[('cadastro', 'api')]
    return CONTRACTS[('universal', 'csv')]


def list_feature_contracts() -> list[FeatureContract]:
    return list(CONTRACTS.values())


__all__ = [
    'API_STEPS',
    'CSV_PRICE_STEPS',
    'CSV_PRODUCT_STEPS',
    'CSV_STOCK_STEPS',
    'CONTRACTS',
    'MODE_ALIASES',
    'OPERATION_ALIASES',
    'STEP_DOWNLOAD',
    'STEP_ENTRADA',
    'STEP_MAPEAMENTO',
    'STEP_MODELO',
    'STEP_ORIGEM',
    'STEP_PRECIFICACAO',
    'STEP_PREVIEW',
    'STEP_REGRAS',
    'UNIVERSAL_STEPS',
    'get_feature_contract',
    'list_feature_contracts',
    'normalize_mode',
    'normalize_operation',
]
