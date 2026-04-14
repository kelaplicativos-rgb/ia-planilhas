from __future__ import annotations

import re
import pandas as pd
from bs4 import BeautifulSoup

from bling_app_zero.core.site_crawler_helpers import (
    texto_limpo_crawler,
    numero_texto_crawler,
    extrair_json_ld_crawler,
    buscar_produto_jsonld_crawler,
    meta_content_crawler,
    primeiro_texto_crawler,
    todas_imagens_crawler,
    detectar_estoque_crawler,
)


# ==========================================================
# EXTRAÇÃO PRINCIPAL DO PRODUTO
# ==========================================================
def extrair_produto(html: str, url: str) -> dict:
    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")

    # =========================
    # JSON-LD (prioridade alta)
    # =========================
    jsonlds = extrair_json_ld_crawler(soup)
    produto_json = buscar_produto_jsonld_crawler(jsonlds)

    # =========================
    # NOME
    # =========================
    nome = (
        produto_json.get("name")
        or meta_content_crawler(soup, "property", "og:title")
        or primeiro_texto_crawler(
            soup,
            [
                "h1",
                ".product-title",
                ".product_name",
                "[class*=title]",
            ],
        )
    )

    nome = texto_limpo_crawler(nome)

    # =========================
    # PREÇO
    # =========================
    preco = ""

    # JSON-LD
    offers = produto_json.get("offers")
    if isinstance(offers, dict):
        preco = offers.get("price") or ""

    if not preco:
        preco = (
            meta_content_crawler(soup, "property", "product:price:amount")
            or primeiro_texto_crawler(
                soup,
                [
                    "[itemprop=price]",
                    ".price",
                    ".preco",
                    "[class*=price]",
                ],
            )
        )

    preco = numero_texto_crawler(preco)

    # =========================
    # GTIN / EAN
    # =========================
    gtin = (
        produto_json.get("gtin13")
        or produto_json.get("gtin")
        or ""
    )

    if not gtin:
        texto_total = texto_limpo_crawler(soup.get_text(" ", strip=True))
        match = re.search(r"\b\d{8,14}\b", texto_total)
        if match:
            gtin = match.group(0)

    # =========================
    # SKU
    # =========================
    sku = produto_json.get("sku") or ""

    # =========================
    # MARCA
    # =========================
    marca = ""
    brand = produto_json.get("brand")

    if isinstance(brand, dict):
        marca = brand.get("name", "")
    elif isinstance(brand, str):
        marca = brand

    # =========================
    # IMAGENS
    # =========================
    imagens = todas_imagens_crawler(soup, url)

    # =========================
    # ESTOQUE (REGRA CRÍTICA)
    # =========================
    estoque = detectar_estoque_crawler(html, soup, padrao=0)

    # =========================
    # DESCRIÇÃO
    # =========================
    descricao = (
        produto_json.get("description")
        or meta_content_crawler(soup, "name", "description")
        or ""
    )

    descricao = texto_limpo_crawler(descricao)

    # =========================
    # RESULTADO FINAL
    # =========================
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


# ==========================================================
# CONVERSÃO PARA DATAFRAME
# ==========================================================
def extrair_produto_df(html: str, url: str) -> pd.DataFrame:
    dados = extrair_produto(html, url)

    if not dados:
        return pd.DataFrame()

    return pd.DataFrame([dados])
