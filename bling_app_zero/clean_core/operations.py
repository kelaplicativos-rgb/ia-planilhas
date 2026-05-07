from __future__ import annotations

from enum import Enum
from typing import Iterable


class Operation(str, Enum):
    CADASTRO = "cadastro"
    ESTOQUE = "estoque"


def normalize_operation(value: str | None) -> Operation:
    text = (value or "").strip().lower()
    if text in {"estoque", "atualização de estoque", "atualizacao de estoque", "atualizar estoque"}:
        return Operation.ESTOQUE
    return Operation.CADASTRO


def detect_operation_from_columns(columns: Iterable[str]) -> Operation:
    joined = " ".join(str(col).strip().lower() for col in columns)
    stock_score = sum(token in joined for token in ("estoque", "quantidade", "saldo", "depósito", "deposito", "balanço", "balanco"))
    cadastro_score = sum(token in joined for token in ("descrição complementar", "categoria", "marca", "imagem", "ncm", "fornecedor"))
    return Operation.ESTOQUE if stock_score > 0 and stock_score >= cadastro_score else Operation.CADASTRO


def operation_label(operation: Operation) -> str:
    return "Atualização de estoque" if operation == Operation.ESTOQUE else "Cadastro de produtos"
