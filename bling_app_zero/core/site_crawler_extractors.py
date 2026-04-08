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
    try:
        from bling_app_zero.utils.excel import log_debug
    except Exception:
        def log_debug(*args, **kwargs):
            pass


# ==========================================================
# HELPERS PESADOS
# ==========================================================
def _limpar_texto(valor: Any) -> str:
    return re.sub(r"\s+", " ", str(valor or "")).strip()


def _extrair_preco_texto_global(html: str) -> str:
    """
    fallback extremo: pega qualquer preço do HTML
    """
    matches = re.findall(r"R\$?\s?\d+[.,]\d{2}", html)
    if matches:
        return numero_texto_crawler(matches[0])
    return ""


def _extrair_nome_texto_global(soup: BeautifulSoup) -> str:
    """
    fallback extremo: pega maior texto relevante
    """
    candidatos = [h.get_text(" ", strip=True) for h in soup.find_all("h1")]
    if candidatos:
        return _limpar_texto(candidatos[0])

    title = soup.title.string if soup.title else ""
    return _limpar_texto(title)


# ==========================================================
# SCORE
# ==========================================================
def _score_produto(dados: dict) -> int:
    score = 0

    if dados.get("Nome"):
        score += 3
    if dados.get("Preço"):
        score += 3
    if dados.get("URL Imagens Externas"):
        score += 2
    if dados.get("Descrição"):
        score += 1
    if dados.get("Marca"):
        score += 1

    return score


# ==========================================================
# EXTRAÇÕES
# ==========================================================
def extrair_nome_crawler(soup: BeautifulSoup, jsonld: dict) -> str:
    nome = texto_limpo_crawler(jsonld.get("name"))
    if nome:
        return nome

    og = meta_content_crawler(soup, "property", "og:title")
    if og:
        return og

    nome = primeiro_texto_crawler(
        soup,
        ["h1", ".product-title", ".product-name", "[itemprop='name']"],
    )
    if nome:
        return nome

    return _extrair_nome_texto_global(soup)


def extrair_preco_crawler(soup: BeautifulSoup, jsonld: dict, html: str) -> str:
    offers = jsonld.get("offers")

    if isinstance(offers, dict) and offers.get("price"):
        return numero_texto_crawler(offers.get("price"))

    if isinstance(offers, list):
        for o in offers:
            if isinstance(o, dict) and o.get("price"):
                return numero_texto_crawler(o.get("price"))

    meta = meta_content_crawler(soup, "property", "product:price:amount")
    if meta:
        return numero_texto_crawler(meta)

    preco = numero_texto_crawler(
        primeiro_texto_crawler(
            soup,
            [
                ".price",
                ".preco",
                ".product-price",
                ".current-price",
                ".sale-price",
                "[data-price]",
            ],
        )
    )

    if preco:
        return preco

    return _extrair_preco_texto_global(html)


def extrair_descricao_crawler(soup: BeautifulSoup, jsonld: dict) -> str:
    desc = texto_limpo_crawler(jsonld.get("description"))
    if desc:
        return desc

    meta = meta_content_crawler(soup, "name", "description")
    if meta:
        return meta

    desc = primeiro_texto_crawler(
        soup,
        [
            ".product-description",
            ".description",
            "#tab-description",
            "[itemprop='description']",
        ],
    )

    if desc:
        return desc

    # fallback pesado
    texto = soup.get_text(" ", strip=True)
    return texto[:1200]


def extrair_marca_crawler(soup: BeautifulSoup, jsonld: dict) -> str:
    marca = jsonld.get("brand")

    if isinstance(marca, dict):
        return texto_limpo_crawler(marca.get("name"))

    if isinstance(marca, str):
        return texto_limpo_crawler(marca)

    return primeiro_texto_crawler(
        soup,
        [".brand", ".marca", "[itemprop='brand']"],
    )


def extrair_gtin_crawler(soup: BeautifulSoup, jsonld: dict) -> str:
    for k in ["gtin13", "gtin12", "gtin14", "gtin8"]:
        if jsonld.get(k):
            return re.sub(r"\D", "", str(jsonld.get(k)))

    texto = primeiro_texto_crawler(soup, [".ean", ".gtin"])
    return re.sub(r"\D", "", texto)


def extrair_ncm_crawler(soup: BeautifulSoup) -> str:
    texto = texto_limpo_crawler(soup.get_text(" ", strip=True))
    m = re.search(r"\bNCM\b[:\s\-]*([0-9\.\-]{8,12})", texto, re.I)
    if m:
        return re.sub(r"\D", "", m.group(1))
    return ""


def extrair_categoria_crawler(soup: BeautifulSoup) -> str:
    partes = []

    for a in soup.select(".breadcrumb a, nav.breadcrumb a"):
        txt = texto_limpo_crawler(a.get_text(" ", strip=True))
        if txt and txt.lower() not in {"home"}:
            partes.append(txt)

    return " > ".join(dict.fromkeys(partes))


# ==========================================================
# EXTRAÇÃO PRINCIPAL
# ==========================================================
def extrair_produto_crawler(
    html: str,
    url: str,
    padrao_disponivel: int = 10,
) -> dict:

    soup = BeautifulSoup(html, "html.parser")

    jsonlds = extrair_json_ld_crawler(soup)
    json_produto = buscar_produto_jsonld_crawler(jsonlds)

    dados = {
        "Nome": extrair_nome_crawler(soup, json_produto),
        "Preço": extrair_preco_crawler(soup, json_produto, html),
        "Descrição": extrair_descricao_crawler(soup, json_produto),
        "Marca": extrair_marca_crawler(soup, json_produto),
        "Categoria": extrair_categoria_crawler(soup),
        "GTIN/EAN": extrair_gtin_crawler(soup, json_produto),
        "NCM": extrair_ncm_crawler(soup),
        "URL Imagens Externas": todas_imagens_crawler(soup, url),
        "Link Externo": url,
        "Estoque": detectar_estoque_crawler(html, soup, padrao_disponivel),
    }

    # DESCRIÇÃO CURTA
    dados["Descrição Curta"] = dados.get("Descrição") or dados.get("Nome")

    score = _score_produto(dados)

    log_debug(f"[EXTRACTOR] Score produto: {score} | URL: {url}")

    if score < 4:
        log_debug(f"[EXTRACTOR] Produto fraco descartado | {url}", "WARNING")
        return {}

    return dados
