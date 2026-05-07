from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class OperationType(str, Enum):
    CADASTRO = "cadastro"
    ESTOQUE = "estoque"


@dataclass(frozen=True)
class OperationProfile:
    operation: OperationType
    title: str
    description: str
    required_hints: tuple[str, ...]
    optional_hints: tuple[str, ...]


CADASTRO_PROFILE = OperationProfile(
    operation=OperationType.CADASTRO,
    title="Cadastro de produtos",
    description="Cria uma planilha de cadastro respeitando exatamente as colunas do modelo anexado.",
    required_hints=("descrição", "descricao", "nome", "produto", "preço", "preco"),
    optional_hints=(
        "código",
        "codigo",
        "sku",
        "gtin",
        "ean",
        "marca",
        "fornecedor",
        "categoria",
        "imagem",
        "url",
        "ncm",
    ),
)

ESTOQUE_PROFILE = OperationProfile(
    operation=OperationType.ESTOQUE,
    title="Atualização de estoque",
    description="Atualiza estoque em motor separado, buscando somente campos de estoque solicitados pelo modelo.",
    required_hints=("produto", "descrição", "descricao", "sku", "código", "codigo", "quantidade", "saldo", "estoque"),
    optional_hints=("depósito", "deposito", "balanço", "balanco", "preço", "preco", "gtin", "ean"),
)


def normalize_operation(value: str | None) -> OperationType:
    raw = (value or "").strip().lower()
    if raw in {"estoque", "atualizacao", "atualização", "atualizar estoque", "stock"}:
        return OperationType.ESTOQUE
    return OperationType.CADASTRO


def get_profile(operation: OperationType | str | None) -> OperationProfile:
    op = normalize_operation(str(operation.value if isinstance(operation, OperationType) else operation))
    return ESTOQUE_PROFILE if op == OperationType.ESTOQUE else CADASTRO_PROFILE


def looks_like_stock_model(columns: Iterable[str]) -> bool:
    joined = " ".join(str(c).lower() for c in columns)
    stock_hits = sum(token in joined for token in ("estoque", "quantidade", "saldo", "depósito", "deposito", "balanço", "balanco"))
    cadastro_hits = sum(token in joined for token in ("descrição complementar", "marca", "categoria", "imagem", "ncm"))
    return stock_hits >= 1 and stock_hits >= cadastro_hits
