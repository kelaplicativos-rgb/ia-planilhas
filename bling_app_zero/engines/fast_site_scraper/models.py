from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FastProductPage:
    url: str
    html: str
    text: str
    jsonld_products: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class FastProductData:
    url: str = ''
    codigo: str = ''
    gtin: str = ''
    descricao: str = ''
    descricao_complementar: str = ''
    ficha_tecnica: str = ''
    caracteristicas: str = ''
    preco: str = ''
    estoque: str = ''
    imagem: str = ''
    marca: str = ''
    categoria: str = ''
