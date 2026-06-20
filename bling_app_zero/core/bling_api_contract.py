from __future__ import annotations

import pandas as pd

from bling_app_zero.universal.model_contract_detector import normalize_contract_operation

OP_CADASTRO = 'cadastro'
OP_ESTOQUE = 'estoque'
OP_ATUALIZACAO_PRECO = 'atualizacao_preco'

DIRECT_OPERATION_LABELS = {
    OP_CADASTRO: 'Cadastrar produtos',
    OP_ESTOQUE: 'Atualizar estoque',
    OP_ATUALIZACAO_PRECO: 'Atualizar preços',
}

API_CONTRACT_COLUMNS = {
    OP_CADASTRO: [
        'Nome',
        'Código',
        'Preço',
        'Quantidade',
        'GTIN',
        'Descrição',
        'Marca',
        'Categoria',
        'Imagens',
        'Depósito',
    ],
    OP_ESTOQUE: ['ID produto', 'Código', 'Quantidade', 'Depósito'],
    OP_ATUALIZACAO_PRECO: ['ID produto', 'Código', 'Preço'],
}


def normalize_direct_operation(value: object, default: str = '') -> str:
    """Normaliza somente operações concretas da API.

    Sem escolha explícita do usuário, retorna vazio. Isso impede que o modo API
    caia automaticamente em cadastro ou universal por cache/compatibilidade.
    """
    operation = normalize_contract_operation(value)
    if operation in DIRECT_OPERATION_LABELS:
        return operation
    fallback = normalize_contract_operation(default)
    return fallback if fallback in DIRECT_OPERATION_LABELS else ''


def direct_operation_label(operation: object) -> str:
    normalized = normalize_direct_operation(operation)
    if normalized in DIRECT_OPERATION_LABELS:
        return DIRECT_OPERATION_LABELS[normalized]
    return str(operation or '').strip()


def direct_operation_options() -> list[str]:
    return list(DIRECT_OPERATION_LABELS.keys())


def direct_api_contract_columns(operation: object | None = None) -> list[str]:
    normalized = normalize_direct_operation(operation)
    if normalized not in API_CONTRACT_COLUMNS:
        return []
    return list(API_CONTRACT_COLUMNS[normalized])


def direct_api_contract_model(operation: object | None = None) -> pd.DataFrame:
    return pd.DataFrame(columns=direct_api_contract_columns(operation))


__all__ = [
    'API_CONTRACT_COLUMNS',
    'DIRECT_OPERATION_LABELS',
    'OP_ATUALIZACAO_PRECO',
    'OP_CADASTRO',
    'OP_ESTOQUE',
    'direct_api_contract_columns',
    'direct_api_contract_model',
    'direct_operation_label',
    'direct_operation_options',
    'normalize_direct_operation',
]
