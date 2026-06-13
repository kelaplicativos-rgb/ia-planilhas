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
LEGACY_OPERATION_ALIASES: Final[dict[str, str]] = {
    '': OP_UNIVERSAL,
    'modelo': OP_UNIVERSAL,
    'modelo_destino': OP_UNIVERSAL,
    'wizard_cadastro_estoque': OP_UNIVERSAL,
    'produtos': OP_CADASTRO,
    'produto': OP_CADASTRO,
    'cadastro_produtos': OP_CADASTRO,
    'cadastro de produtos': OP_CADASTRO,
    'cadastrar produtos': OP_CADASTRO,
    'estoque': OP_ESTOQUE,
    'stock': OP_ESTOQUE,
    'saldo': OP_ESTOQUE,
    'saldos': OP_ESTOQUE,
    'atualizar estoque': OP_ESTOQUE,
    'atualizacao_estoque': OP_ESTOQUE,
    'preco': OP_ATUALIZACAO_PRECO,
    'precos': OP_ATUALIZACAO_PRECO,
    'price': OP_ATUALIZACAO_PRECO,
    'prices': OP_ATUALIZACAO_PRECO,
    'atualizacao_preco': OP_ATUALIZACAO_PRECO,
    'atualizacao_precos': OP_ATUALIZACAO_PRECO,
    'atualizar preco': OP_ATUALIZACAO_PRECO,
    'atualizar precos': OP_ATUALIZACAO_PRECO,
}
MODEL_OPERATION_BY_TYPE: Final[dict[str, str]] = {
    MODEL_TYPE_CADASTRO: OP_CADASTRO,
    MODEL_TYPE_ESTOQUE: OP_ESTOQUE,
    MODEL_TYPE_PRECOS: OP_ATUALIZACAO_PRECO,
}
OPERATION_LABELS: Final[dict[str, str]] = {
    OP_UNIVERSAL: 'Modelo para mapear',
    OP_CADASTRO: 'Cadastro de produtos',
    OP_ESTOQUE: 'Atualizacao de estoque',
    OP_ATUALIZACAO_PRECO: 'Atualizacao de precos',
}
OPERATION_BADGES: Final[dict[str, str]] = {
    OP_UNIVERSAL: 'Modelo mapeado',
    OP_CADASTRO: 'Cadastro',
    OP_ESTOQUE: 'Estoque',
    OP_ATUALIZACAO_PRECO: 'Precos',
}


@dataclass(frozen=True)
class OperationContract:
    operation: str
    label: str
    badge: str


def _norm(value: object) -> str:
    text = str(value or '').strip().lower()
    replacements = {
        'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a',
        'é': 'e', 'ê': 'e', 'í': 'i',
        'ó': 'o', 'ô': 'o', 'õ': 'o',
        'ú': 'u', 'ç': 'c',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return ' '.join(text.replace('-', '_').replace('/', '_').split())


def normalize_operation(value: object, *, default: str = OP_UNIVERSAL) -> str:
    raw = str(value or '').strip().lower()
    normalized = _norm(raw)
    if raw in VALID_OPERATIONS:
        return raw
    if normalized in VALID_OPERATIONS:
        return normalized
    if raw in LEGACY_OPERATION_ALIASES:
        return LEGACY_OPERATION_ALIASES[raw]
    if normalized in LEGACY_OPERATION_ALIASES:
        return LEGACY_OPERATION_ALIASES[normalized]
    if 'estoque' in normalized or 'saldo' in normalized or 'stock' in normalized:
        return OP_ESTOQUE
    if 'preco' in normalized or 'price' in normalized:
        return OP_ATUALIZACAO_PRECO
    if 'cadastro' in normalized or 'produto' in normalized:
        return OP_CADASTRO
    return default if default in VALID_OPERATIONS else OP_UNIVERSAL


def operation_from_model_type(model_type: object, *, default: str = OP_UNIVERSAL) -> str:
    normalized = _norm(model_type)
    return MODEL_OPERATION_BY_TYPE.get(normalized, normalize_operation(model_type, default=default))


def operation_label(operation: object) -> str:
    return OPERATION_LABELS.get(normalize_operation(operation), OPERATION_LABELS[OP_UNIVERSAL])


def operation_badge(operation: object) -> str:
    return OPERATION_BADGES.get(normalize_operation(operation), OPERATION_BADGES[OP_UNIVERSAL])


def operation_contract(operation: object) -> OperationContract:
    normalized = normalize_operation(operation)
    return OperationContract(operation=normalized, label=operation_label(normalized), badge=operation_badge(normalized))


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
