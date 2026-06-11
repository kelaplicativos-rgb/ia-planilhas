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

VALID_OPERATIONS: Final[set[str]] = {OP_UNIVERSAL, OP_CADASTRO, OP_ESTOQUE, OP_ATUALIZACAO_PRECO}
LEGACY_OPERATION_ALIASES: Final[dict[str, str]] = {'': OP_UNIVERSAL}
MODEL_OPERATION_BY_TYPE: Final[dict[str, str]] = {
    MODEL_TYPE_CADASTRO: OP_UNIVERSAL,
    MODEL_TYPE_ESTOQUE: OP_UNIVERSAL,
    MODEL_TYPE_PRECOS: OP_UNIVERSAL,
}
OPERATION_LABELS: Final[dict[str, str]] = {
    OP_UNIVERSAL: 'Modelo para mapear',
    OP_CADASTRO: 'Modelo para mapear',
    OP_ESTOQUE: 'Modelo para mapear',
    OP_ATUALIZACAO_PRECO: 'Modelo para mapear',
}
OPERATION_BADGES: Final[dict[str, str]] = {
    OP_UNIVERSAL: 'Modelo mapeado',
    OP_CADASTRO: 'Modelo mapeado',
    OP_ESTOQUE: 'Modelo mapeado',
    OP_ATUALIZACAO_PRECO: 'Modelo mapeado',
}


@dataclass(frozen=True)
class OperationContract:
    operation: str
    label: str
    badge: str


def normalize_operation(value: object, *, default: str = OP_UNIVERSAL) -> str:
    return OP_UNIVERSAL


def operation_from_model_type(model_type: object, *, default: str = OP_UNIVERSAL) -> str:
    return OP_UNIVERSAL


def operation_label(operation: object) -> str:
    return OPERATION_LABELS[OP_UNIVERSAL]


def operation_badge(operation: object) -> str:
    return OPERATION_BADGES[OP_UNIVERSAL]


def operation_contract(operation: object) -> OperationContract:
    return OperationContract(operation=OP_UNIVERSAL, label=operation_label(operation), badge=operation_badge(operation))


def is_price_update_operation(operation: object) -> bool:
    return False


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
