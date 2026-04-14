from __future__ import annotations

import re

from bs4 import BeautifulSoup

from bling_app_zero.core.site_crawler_helpers import (
    buscar_produto_jsonld_crawler,
    detectar_estoque_crawler,
    extrair_json_ld_crawler,
    meta_content_crawler,
    numero_texto_crawler,
    primeiro_texto_crawler,
    texto_limpo_crawler,
    todas_imagens_crawler,
)


def carregar_contexto_produto(html: str):
    if not html:
        return None, [], {}

    soup = BeautifulSoup(html, "html.parser")
    jsonlds = extrair_json_ld_crawler(soup)
    produto_json = buscar_produto_jsonld_crawler(jsonlds)

    if not isinstance(produto_json, dict):
        produto_json = {}

    return soup, jsonlds, produto_json


def extrair_nome_produto(soup: BeautifulSoup, produto_json: dict) -> str:
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
    return texto_limpo_crawler(nome)


def extrair_preco_produto(soup: BeautifulSoup, produto_json: dict) -> str:
    preco = ""

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

    return numero_texto_crawler(preco)


def extrair_gtin_produto(soup: BeautifulSoup, produto_json: dict) -> str:
    gtin = produto_json.get("gtin13") or produto_json.get("gtin") or ""

    if gtin:
        return str(gtin).strip()

    texto_total = texto_limpo_crawler(soup.get_text(" ", strip=True))
    match = re.search(r"\b\d{8,14}\b", texto_total)
    if match:
        return match.group(0)

    return ""


def extrair_sku_produto(produto_json: dict) -> str:
    return texto_limpo_crawler(produto_json.get("sku") or "")


def extrair_marca_produto(produto_json: dict) -> str:
    brand = produto_json.get("brand")

    if isinstance(brand, dict):
        return texto_limpo_crawler(brand.get("name", ""))

    if isinstance(brand, str):
        return texto_limpo_crawler(brand)

    return ""


def extrair_descricao_produto(soup: BeautifulSoup, produto_json: dict) -> str:
    descricao = (
        produto_json.get("description")
        or meta_content_crawler(soup, "name", "description")
        or ""
    )
    return texto_limpo_crawler(descricao)


def extrair_imagens_produto(soup: BeautifulSoup, url: str) -> str:
    return todas_imagens_crawler(soup, url)


def extrair_estoque_produto(html: str, soup: BeautifulSoup) -> int:
    return detectar_estoque_crawler(html, soup, padrao=0)
