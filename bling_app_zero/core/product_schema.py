from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List


PRODUCT_MASTER_COLUMNS: List[str] = [
    "sku",
    "descricao",
    "descricao_curta",
    "descricao_complementar",
    "gtin",
    "ncm",
    "marca",
    "categoria",
    "preco_custo",
    "preco_venda",
    "estoque",
    "deposito",
    "imagens",
    "origem",
    "fornecedor",
    "status_validacao",
    "alertas_validacao",
]


@dataclass
class ProductMaster:
    sku: str = ""
    descricao: str = ""
    descricao_curta: str = ""
    descricao_complementar: str = ""
    gtin: str = ""
    ncm: str = ""
    marca: str = ""
    categoria: str = ""
    preco_custo: float = 0.0
    preco_venda: float = 0.0
    estoque: float = 0.0
    deposito: str = ""
    imagens: str = ""
    origem: str = ""
    fornecedor: str = ""
    status_validacao: str = "pendente"
    alertas_validacao: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def empty_product_dict() -> Dict[str, Any]:
    return ProductMaster().to_dict()
