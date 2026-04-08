from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from bling_app_zero.core.site_crawler_helpers import (
    buscar_produto_jsonld_crawler,
    detectar_estoque_crawler,
    extrair_json_ld_crawler,
    meta_content_crawler,
    numero_texto_crawler,
    primeiro_texto_crawler,
    todas_imagens_crawler,
    texto_limpo_crawler,
)

# ==========================================================
# LOG
# ==========================================================
try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    def log_debug(*args, **kwargs):
        pass


# ==========================================================
# HELPERS
# ==========================================================
def _limpar(valor: Any) -> str:
    return re.sub(r"\s+", " ", str(valor or "")).strip()


def _digitos(valor: Any) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def _extrair_preco_global(html: str) -> str:
    matches = re.findall(r"R\$\s*\d[\d\.\,]*", html or "", re.I)
    for m in matches:
        p = numero_texto_crawler(m)
        if p:
            return p
    return ""


def _extrair_categoria(soup: BeautifulSoup) -> str:
    partes = []

    for a in soup.select("a"):
        txt = texto_limpo_crawler(a.get_text(" ", strip=True))
        if txt and len(txt) < 40:
            if any(x in txt.lower() for x in ["categoria", "produtos"]):
                continue
            partes.append(txt)

    return " > ".join(dict.fromkeys(partes[:4]))


# ==========================================================
# EXTRAÇÃO PRINCIPAL
# ==========================================================
def extrair_nome(soup, jsonld):
    return (
        texto_limpo_crawler(jsonld.get("name"))
        or meta_content_crawler(soup, "property", "og:title")
        or primeiro_texto_crawler(
            soup,
            [
                "h1",
                ".product-title",
                ".product-name",
                ".title",
                "[class*='title']",
            ],
        )
    )


def extrair_preco(soup, jsonld, html):
    offers = jsonld.get("offers")

    if isinstance(offers, dict):
        preco = numero_texto_crawler(offers.get("price"))
        if preco:
            return preco

    if isinstance(offers, list):
        for o in offers:
            preco = numero_texto_crawler(o.get("price"))
            if preco:
                return preco

    meta = meta_content_crawler(soup, "property", "product:price:amount")
    if meta:
        return numero_texto_crawler(meta)

    seletores = [
        "[class*='price']",
        "[class*='valor']",
        "[data-price]",
        ".price",
    ]

    for sel in seletores:
        el = soup.select_one(sel)
        if el:
            preco = numero_texto_crawler(el.get_text())
            if preco and len(preco) >= 2:
                return preco

    return _extrair_preco_global(html)


def extrair_descricao(soup, jsonld):
    desc = texto_limpo_crawler(jsonld.get("description"))
    if desc:
        return desc

    meta = meta_content_crawler(soup, "name", "description")
    if meta:
        return meta

    for sel in [
        ".product-description",
        ".description",
        "[class*='description']",
    ]:
        el = soup.select_one(sel)
        if el:
            txt = texto_limpo_crawler(el.get_text())
            if txt:
                return txt

    return ""


def extrair_imagens(soup, url, jsonld):
    imgs = jsonld.get("image")

    if isinstance(imgs, list):
        return " | ".join([i for i in imgs if isinstance(i, str)])

    if isinstance(imgs, str):
        return imgs

    return todas_imagens_crawler(soup, url)


def extrair_marca(jsonld):
    marca = jsonld.get("brand")

    if isinstance(marca, dict):
        return texto_limpo_crawler(marca.get("name"))

    if isinstance(marca, str):
        return texto_limpo_crawler(marca)

    return ""


# ==========================================================
# MAIN
# ==========================================================
def extrair_produto_crawler(
    html: str,
    url: str,
    padrao_disponivel: int = 10,
    network_records=None,
    payload_origem=None,
) -> dict:

    soup = BeautifulSoup(html, "html.parser")

    jsonlds = extrair_json_ld_crawler(soup)
    json_produto = buscar_produto_jsonld_crawler(jsonlds)

    base = {
        "Nome": extrair_nome(soup, json_produto),
        "Preço": extrair_preco(soup, json_produto, html),
        "Descrição": extrair_descricao(soup, json_produto),
        "Marca": extrair_marca(json_produto),
        "Categoria": _extrair_categoria(soup),
        "GTIN/EAN": _digitos(json_produto.get("gtin13")),
        "URL Imagens Externas": extrair_imagens(soup, url, json_produto),
        "Link Externo": url,
        "Estoque": detectar_estoque_crawler(html, soup, padrao_disponivel),
    }

    base["Descrição Curta"] = base.get("Descrição") or base.get("Nome")

    if not base.get("Nome"):
        return {}

    log_debug(f"[EXTRACTOR FINAL] {url}")

    return base
