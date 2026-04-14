from __future__ import annotations

import pandas as pd

from bling_app_zero.scrapers.extrator_produto_campos import (
    carregar_contexto_produto,
    extrair_descricao_produto,
    extrair_estoque_produto,
    extrair_gtin_produto,
    extrair_imagens_produto,
    extrair_marca_produto,
    extrair_nome_produto,
    extrair_preco_produto,
    extrair_sku_produto,
)


def extrair_produto(html: str, url: str) -> dict:
    if not html:
        return {}

    soup, _jsonlds, produto_json = carregar_contexto_produto(html)
    if soup is None:
        return {}

    nome = extrair_nome_produto(soup, produto_json)
    preco = extrair_preco_produto(soup, produto_json)
    gtin = extrair_gtin_produto(soup, produto_json)
    sku = extrair_sku_produto(produto_json)
    marca = extrair_marca_produto(produto_json)
    descricao = extrair_descricao_produto(soup, produto_json)
    imagens = extrair_imagens_produto(soup, url)
    estoque = extrair_estoque_produto(html, soup)

    return {
        "url": url,
        "nome": nome,
        "preco": preco,
        "gtin": gtin,
        "sku": sku,
        "marca": marca,
        "descricao": descricao,
        "imagens": imagens,
        "estoque": estoque,
    }


def extrair_produto_df(html: str, url: str) -> pd.DataFrame:
    dados = extrair_produto(html, url)

    if not dados:
        return pd.DataFrame()

    return pd.DataFrame([dados])
