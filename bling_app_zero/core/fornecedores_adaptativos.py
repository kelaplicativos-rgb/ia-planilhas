from __future__ import annotations

from typing import Any

from .fornecedores_adaptativos_detectores import analisar_fornecedor_por_html
from .fornecedores_adaptativos_storage import (
    atualizar_fornecedor,
    carregar_fornecedor,
    extrair_dominio,
    listar_fornecedores,
    salvar_fornecedor,
)


def garantir_fornecedor_adaptativo(url: str, html: str) -> dict[str, Any]:
    dominio = extrair_dominio(url)
    if not dominio:
        return {}

    existente = carregar_fornecedor(dominio)
    if existente:
        return existente

    config = analisar_fornecedor_por_html(url, html)
    salvar_fornecedor(dominio, config, sobrescrever=False)
    return carregar_fornecedor(dominio) or config


__all__ = [
    "extrair_dominio",
    "carregar_fornecedor",
    "listar_fornecedores",
    "salvar_fornecedor",
    "atualizar_fornecedor",
    "analisar_fornecedor_por_html",
    "garantir_fornecedor_adaptativo",
]
