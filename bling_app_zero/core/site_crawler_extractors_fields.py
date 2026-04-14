from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from bling_app_zero.core.site_crawler_helpers import (
    meta_content_crawler,
    numero_texto_crawler,
    primeiro_texto_crawler,
    texto_limpo_crawler,
)
from bling_app_zero.core.site_crawler_extractors_utils import (
    _extrair_preco_global,
    _limpar_descricao,
)


def extrair_nome(soup: BeautifulSoup, jsonld: dict[str, Any]) -> str:
    return (
        texto_limpo_crawler(jsonld.get("name"))
        or meta_content_crawler(soup, "property", "og:title")
        or primeiro_texto_crawler(
            soup,
            [
                "h1",
                ".product-title",
                ".product-name",
                "[class*='product'] h1",
                "[class*='title']",
            ],
        )
    )


def extrair_preco(soup: BeautifulSoup, jsonld: dict[str, Any], html: str) -> str:
    offers = jsonld.get("offers")

    if isinstance(offers, dict):
        preco = numero_texto_crawler(offers.get("price"))
        if preco:
            return preco

    if isinstance(offers, list):
        for offer in offers:
            preco = numero_texto_crawler((offer or {}).get("price"))
            if preco:
                return preco

    meta = meta_content_crawler(soup, "property", "product:price:amount")
    if meta:
        return numero_texto_crawler(meta)

    for el in soup.select("[class*='price'], [class*='valor']"):
        txt = texto_limpo_crawler(el.get_text())
        preco = numero_texto_crawler(txt)
        if preco and len(preco) >= 3:
            return preco

    return _extrair_preco_global(html)


def extrair_descricao(soup: BeautifulSoup, jsonld: dict[str, Any]) -> str:
    desc = texto_limpo_crawler(jsonld.get("description"))

    if not desc:
        meta = meta_content_crawler(soup, "name", "description")
        desc = meta or ""

    if not desc:
        for sel in [
            ".product-description",
            ".description",
            "[class*='description']",
        ]:
            el = soup.select_one(sel)
            if el:
                desc = texto_limpo_crawler(el.get_text())
                break

    return _limpar_descricao(desc)


def extrair_marca(jsonld: dict[str, Any]) -> str:
    marca = jsonld.get("brand")

    if isinstance(marca, dict):
        return texto_limpo_crawler(marca.get("name"))

    if isinstance(marca, str):
        return texto_limpo_crawler(marca)

    return ""
