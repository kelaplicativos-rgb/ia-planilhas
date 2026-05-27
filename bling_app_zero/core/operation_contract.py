from __future__ import annotations

from dataclasses import dataclass
from typing import Final

OP_CADASTRO: Final[str] = 'cadastro'
OP_ESTOQUE: Final[str] = 'estoque'
OP_ATUALIZACAO_PRECO: Final[str] = 'atualizacao_preco'
OP_UNIVERSAL: Final[str] = 'universal'

MODEL_TYPE_CADASTRO: Final[str] = 'cadastro'
MODEL_TYPE_ESTOQUE: Final[str] = 'estoque'
MODEL_TYPE_PRECOS: Final[str] = 'precos'

VALID_OPERATIONS: Final[set[str]] = {
    OP_CADASTRO,
    OP_ESTOQUE,
    OP_ATUALIZACAO_PRECO,
    OP_UNIVERSAL,
}

LEGACY_OPERATION_ALIASES: Final[dict[str, str]] = {
    '': OP_UNIVERSAL,
    'modelo': OP_UNIVERSAL,
    'modelo_destino': OP_UNIVERSAL,
    'planilha': OP_UNIVERSAL,
    'wizard_cadastro_estoque': OP_UNIVERSAL,
    'preco': OP_ATUALIZACAO_PRECO,
    'precos': OP_ATUALIZACAO_PRECO,
    'atualizar_precos': OP_ATUALIZACAO_PRECO,
    'atualizacao_precos': OP_ATUALIZACAO_PRECO,
    'atualização_preço': OP_ATUALIZACAO_PRECO,
    'atualização_precos': OP_ATUALIZACAO_PRECO,
    'atualização_preços': OP_ATUALIZACAO_PRECO,
}

MODEL_OPERATION_BY_TYPE: Final[dict[str, str]] = {
    MODEL_TYPE_CADASTRO: OP_CADASTRO,
    MODEL_TYPE_ESTOQUE: OP_ESTOQUE,
    MODEL_TYPE_PRECOS: OP_ATUALIZACAO_PRECO,
}

OPERATION_LABELS: Final[dict[str, str]] = {
    OP_CADASTRO: 'Cadastro de produtos',
    OP_ESTOQUE: 'Atualização de estoque',
    OP_ATUALIZACAO_PRECO: 'Atualização de preços',
    OP_UNIVERSAL: 'Modelo final preenchido',
}

OPERATION_BADGES: Final[dict[str, str]] = {
    OP_CADASTRO: '📄 CSV BLING · CADASTRO',
    OP_ESTOQUE: '📦 CSV BLING · ESTOQUE',
    OP_ATUALIZACAO_PRECO: '💲 CSV BLING · PREÇOS',
    OP_UNIVERSAL: '📄 CSV BLING · MODELO FINAL',
}


@dataclass(frozen=True)
class OperationContract:
    operation: str
    label: str
    badge: str


def normalize_operation(value: object, *, default: str = OP_UNIVERSAL) -> str:
    text = str(value or '').strip().lower()
    if text in VALID_OPERATIONS:
        return text
    if text in LEGACY_OPERATION_ALIASES:
        return LEGACY_OPERATION_ALIASES[text]
    return default


def operation_from_model_type(model_type: object, *, default: str = OP_UNIVERSAL) -> str:
    text = str(model_type or '').strip().lower()
    return MODEL_OPERATION_BY_TYPE.get(text, default)


def operation_label(operation: object) -> str:
    return OPERATION_LABELS.get(normalize_operation(operation), OPERATION_LABELS[OP_UNIVERSAL])


def operation_badge(operation: object) -> str:
    return OPERATION_BADGES.get(normalize_operation(operation), OPERATION_BADGES[OP_UNIVERSAL])


def operation_contract(operation: object) -> OperationContract:
    normalized = normalize_operation(operation)
    return OperationContract(
        operation=normalized,
        label=operation_label(normalized),
        badge=operation_badge(normalized),
    )


def is_price_update_operation(operation: object) -> bool:
    return normalize_operation(operation) == OP_ATUALIZACAO_PRECO


__all__ = [
    'LEGACY_OPERATION_ALIASES',
    'MODEL_OPERATION_BY_TYPE',
    'MODEL_TYPE_CADASTRO',
    'MODEL_TYPE_ESTOQUE',
    'MODEL_TYPE_PRECOS',
    'OP_ATUALIZACAO_PRECO',
    'OP_CADASTRO',
    'OP_ESTOQUE',
    'OP_UNIVERSAL',
    'OPERATION_BADGES',
    'OPERATION_LABELS',
    'OperationContract',
    'VALID_OPERATIONS',
    'is_price_update_operation',
    'normalize_operation',
    'operation_badge',
    'operation_contract',
    'operation_from_model_type',
    'operation_label',
]
