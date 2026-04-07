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
    todas_imagens_crawler,
    texto_limpo_crawler,
)


def extrair_marca_crawler(soup: BeautifulSoup, jsonld_produto: dict) -> str:
    marca_json = jsonld_produto.get("brand")
    if isinstance(marca_json, dict):
        nome = texto_limpo_crawler(marca_json.get("name"))
        if nome:
            return nome
    elif isinstance(marca_json, str):
        nome = texto_limpo_crawler(marca_json)
        if nome:
            return nome

    texto = primeiro_texto_crawler(
        soup,
        [
            ".brand",
            ".product-brand",
            ".marca",
            "[itemprop='brand']",
        ],
    )
    return texto


def extrair_categoria_crawler(soup: BeautifulSoup) -> str:
    partes = []
    for seletor in [".breadcrumb a", ".breadcrumbs a", "nav.breadcrumb a"]:
        try:
            for a in soup.select(seletor):
                txt = texto_limpo_crawler(a.get_text(" ", strip=True))
                if txt and txt.lower() not in {"home", "início", "inicio"}:
                    partes.append(txt)
        except Exception:
            continue

    unicos = []
    for item in partes:
        if item not in unicos:
            unicos.append(item)

    return " > ".join(unicos[:5])


def extrair_gtin_crawler(soup: BeautifulSoup, jsonld_produto: dict) -> str:
    for chave in ["gtin13", "gtin12", "gtin14", "gtin8", "gtin"]:
        valor = jsonld_produto.get(chave)
        if valor:
            return re.sub(r"\D", "", str(valor))

    texto = primeiro_texto_crawler(
        soup,
        [
            "[itemprop='gtin13']",
            "[itemprop='gtin12']",
            "[itemprop='gtin14']",
            ".ean",
            ".gtin",
        ],
    )
    return re.sub(r"\D", "", texto)


def extrair_ncm_crawler(soup: BeautifulSoup) -> str:
    texto_total = texto_limpo_crawler(soup.get_text(" ", strip=True))
    match = re.search(r"\bNCM\b[:\s\-]*([0-9\.\-]{8,12})", texto_total, flags=re.I)
    if match:
        return re.sub(r"\D", "", match.group(1))
    return ""


def extrair_preco_crawler(soup: BeautifulSoup, jsonld_produto: dict) -> str:
    offers = jsonld_produto.get("offers")
    if isinstance(offers, dict):
        preco = offers.get("price")
        if preco:
            return numero_texto_crawler(preco)

    if isinstance(offers, list):
        for item in offers:
            if isinstance(item, dict) and item.get("price"):
                return numero_texto_crawler(item.get("price"))

    meta_preco = meta_content_crawler(soup, "property", "product:price:amount")
    if meta_preco:
        return numero_texto_crawler(meta_preco)

    return numero_texto_crawler(
        primeiro_texto_crawler(
            soup,
            [
                ".price",
                ".preco",
                ".product-price",
                ".current-price",
                ".sale-price",
                ".woocommerce-Price-amount",
                "[data-price]",
            ],
        )
    )


def extrair_nome_crawler(soup: BeautifulSoup, jsonld_produto: dict) -> str:
    nome = texto_limpo_crawler(jsonld_produto.get("name"))
    if nome:
        return nome

    og = meta_content_crawler(soup, "property", "og:title")
    if og:
        return og

    return primeiro_texto_crawler(
        soup,
        [
            "h1",
            ".product-title",
            ".product-name",
            ".entry-title",
            "[itemprop='name']",
        ],
    )


def extrair_descricao_crawler(soup: BeautifulSoup, jsonld_produto: dict) -> str:
    desc = texto_limpo_crawler(jsonld_produto.get("description"))
    if desc:
        return desc

    meta_desc = meta_content_crawler(soup, "name", "description")
    if meta_desc:
        return meta_desc

    return primeiro_texto_crawler(
        soup,
        [
            ".product-description",
            ".description",
            ".woocommerce-product-details__short-description",
            "#tab-description",
            "[itemprop='description']",
        ],
    )


def extrair_produto_crawler(
    html: str,
    url: str,
    padrao_disponivel: int = 10,
) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    jsonlds = extrair_json_ld_crawler(soup)
    produto_json = buscar_produto_jsonld_crawler(jsonlds)

    nome = extrair_nome_crawler(soup, produto_json)
    preco = extrair_preco_crawler(soup, produto_json)
    descricao = extrair_descricao_crawler(soup, produto_json)
    imagens = todas_imagens_crawler(soup, url)
    marca = extrair_marca_crawler(soup, produto_json)
    categoria = extrair_categoria_crawler(soup)
    gtin = extrair_gtin_crawler(soup, produto_json)
    ncm = extrair_ncm_crawler(soup)
    estoque = detectar_estoque_crawler(html, soup, padrao_disponivel=padrao_disponivel)

    return {
        "Nome": nome,
        "Preço": preco,
        "Descrição": descricao,
        "Descrição Curta": descricao,
        "Marca": marca,
        "Categoria": categoria,
        "GTIN/EAN": gtin,
        "NCM": ncm,
        "URL Imagens Externas": imagens,
        "Link Externo": url,
        "Estoque": estoque,
    }
