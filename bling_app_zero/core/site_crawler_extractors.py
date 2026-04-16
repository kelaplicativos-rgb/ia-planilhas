
from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

from bling_app_zero.core.site_crawler_cleaners import (
    descricao_detalhada_valida,
    extrair_preco,
    fornecedor_cfg,
    imagem_valida,
    mesmo_dominio,
    normalizar_imagens,
    normalizar_preco_para_planilha,
    normalizar_texto,
    safe_str,
)
from urllib.parse import urljoin


def texto_por_selectors(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        try:
            el = soup.select_one(selector)
            if el:
                if el.name == "meta":
                    content = safe_str(el.get("content"))
                    if content:
                        return content
                txt = safe_str(el.get_text(" ", strip=True))
                if txt:
                    return txt
        except Exception:
            continue
    return ""


def imagens_por_selectors(url_produto: str, soup: BeautifulSoup, selectors: list[str]) -> list[str]:
    imagens = []
    vistos = set()

    for selector in selectors:
        try:
            for el in soup.select(selector):
                src = safe_str(
                    el.get("content")
                    or el.get("src")
                    or el.get("data-src")
                    or el.get("data-lazy-src")
                    or el.get("data-zoom-image")
                )
                if not src:
                    continue

                url_img = urljoin(url_produto, src)
                if not imagem_valida(url_img):
                    continue
                if url_img in vistos:
                    continue

                vistos.add(url_img)
                imagens.append(url_img)
        except Exception:
            continue

    return imagens


def extrair_json_ld(soup: BeautifulSoup) -> list[dict]:
    itens = []

    for script in soup.select("script[type='application/ld+json']"):
        bruto = safe_str(script.string or script.get_text(" ", strip=True))
        if not bruto:
            continue

        try:
            data = json.loads(bruto)
        except Exception:
            continue

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    itens.append(item)
        elif isinstance(data, dict):
            itens.append(data)

    return itens


def achatar_json_ld_produtos(itens: list[dict]) -> list[dict]:
    produtos = []

    def visitar(node: Any) -> None:
        if isinstance(node, dict):
            tipo = normalizar_texto(node.get("@type"))
            if "product" in tipo:
                produtos.append(node)

            for valor in node.values():
                visitar(valor)

        elif isinstance(node, list):
            for item in node:
                visitar(item)

    for item in itens:
        visitar(item)

    return produtos


def extrair_produto_json_ld(soup: BeautifulSoup, url_produto: str) -> dict:
    itens = extrair_json_ld(soup)
    produtos = achatar_json_ld_produtos(itens)

    if not produtos:
        return {}

    prod = produtos[0]

    nome = safe_str(prod.get("name"))
    sku = safe_str(prod.get("sku"))
    gtin = (
        safe_str(prod.get("gtin13"))
        or safe_str(prod.get("gtin14"))
        or safe_str(prod.get("gtin12"))
        or safe_str(prod.get("gtin8"))
        or safe_str(prod.get("gtin"))
    )
    ncm = safe_str(prod.get("ncm"))

    categoria = safe_str(prod.get("category"))
    descricao = safe_str(prod.get("description"))

    imagens = prod.get("image", [])
    if isinstance(imagens, str):
        imagens = [imagens]
    if not isinstance(imagens, list):
        imagens = []

    imagens = [
        urljoin(url_produto, safe_str(img))
        for img in imagens
        if safe_str(img) and imagem_valida(urljoin(url_produto, safe_str(img)))
    ]

    preco = ""
    quantidade = ""

    offers = prod.get("offers")
    if isinstance(offers, list) and offers:
        offers = offers[0]

    if isinstance(offers, dict):
        preco = safe_str(offers.get("price"))
        disponibilidade = normalizar_texto(offers.get("availability"))
        if "outofstock" in disponibilidade:
            quantidade = "0"

    return {
        "codigo": sku,
        "descricao": nome,
        "descricao_detalhada": descricao,
        "categoria": categoria,
        "gtin": gtin,
        "ncm": ncm,
        "preco": normalizar_preco_para_planilha(preco),
        "quantidade": quantidade,
        "url_imagens": normalizar_imagens("|".join(imagens[:12])),
        "fonte_extracao": "json_ld",
    }


def extrair_breadcrumb(soup: BeautifulSoup) -> str:
    breadcrumb = []

    for el in soup.select(
        "nav a, .breadcrumb a, [class*=breadcrumb] a, ol.breadcrumb li, ul.breadcrumb li"
    ):
        txt = safe_str(el.get_text(" ", strip=True))
        if not txt:
            continue
        txt_n = txt.lower()
        if txt_n in {"home", "início", "inicio"}:
            continue
        if re.fullmatch(r"\d+", txt_n):
            continue
        breadcrumb.append(txt)

    breadcrumb_limpo = []
    vistos = set()
    for item in breadcrumb:
        if item not in vistos:
            vistos.add(item)
            breadcrumb_limpo.append(item)

    categoria = " > ".join(breadcrumb_limpo).strip()
    if re.fullmatch(r"[\d\s>\-]+", categoria):
        return ""
    return categoria


def extrair_detalhes_heuristicos(url_produto: str, html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    cfg = fornecedor_cfg(url_produto)

    json_ld_data = extrair_produto_json_ld(soup, url_produto)

    title_selectors = cfg.get(
        "title_selectors",
        [
            "h1",
            ".product_title",
            ".product-name",
            ".entry-title",
            "[class*='product-title']",
            "[itemprop='name']",
            "meta[property='og:title']",
            "title",
        ],
    )

    price_selectors = cfg.get(
        "price_selectors",
        [
            ".price",
            ".product-price",
            "[class*='price']",
            "[itemprop='price']",
            "[data-price]",
            "meta[property='product:price:amount']",
        ],
    )

    image_selectors = cfg.get(
        "image_selectors",
        [
            "meta[property='og:image']",
            "img[src]",
            "img[data-src]",
            "img[data-lazy-src]",
            ".product-gallery img[src]",
            ".woocommerce-product-gallery img[src]",
        ],
    )

    titulo = texto_por_selectors(soup, title_selectors) or json_ld_data.get("descricao", "")
    texto_total = soup.get_text(" ", strip=True)

    preco = texto_por_selectors(soup, price_selectors)
    if not preco:
        preco = extrair_preco(texto_total)
    preco = normalizar_preco_para_planilha(preco) or json_ld_data.get("preco", "")

    imagens = imagens_por_selectors(url_produto, soup, image_selectors)
    if not imagens and json_ld_data.get("url_imagens"):
        imagens = [x for x in json_ld_data.get("url_imagens", "").split("|") if imagem_valida(x)]

    if not imagens:
        for img in soup.find_all("img"):
            src = safe_str(img.get("src") or img.get("data-src") or img.get("data-lazy-src"))
            if not src:
                continue
            url_img = urljoin(url_produto, src)
            if not mesmo_dominio(url_produto, url_img):
                continue
            if not imagem_valida(url_img):
                continue
            imagens.append(url_img)
            if len(imagens) >= 12:
                break

    codigo = json_ld_data.get("codigo", "")
    gtin = json_ld_data.get("gtin", "")
    ncm = json_ld_data.get("ncm", "")

    padroes_codigo = [
        r"(?:sku|c[oó]d(?:igo)?|refer[eê]ncia)[\s:\-#]*([A-Za-z0-9\-_\.\/]+)",
    ]
    padroes_gtin = [
        r"(?:gtin|ean|c[oó]digo de barras)[\s:\-#]*([0-9]{8,14})",
    ]
    padroes_ncm = [
        r"(?:ncm)[\s:\-#]*([0-9\.]{6,10})",
    ]

    if not codigo:
        for padrao in padroes_codigo:
            m = re.search(padrao, texto_total, flags=re.I)
            if m:
                codigo = safe_str(m.group(1))
                break

    if not gtin:
        for padrao in padroes_gtin:
            m = re.search(padrao, texto_total, flags=re.I)
            if m:
                gtin = safe_str(m.group(1))
                break

    if not ncm:
        for padrao in padroes_ncm:
            m = re.search(padrao, texto_total, flags=re.I)
            if m:
                ncm = safe_str(m.group(1))
                break

    categoria = extrair_breadcrumb(soup) or json_ld_data.get("categoria", "")
    if re.fullmatch(r"[\d\s>\-]+", safe_str(categoria)):
        categoria = ""

    estoque = json_ld_data.get("quantidade", "")
    texto_total_n = texto_total.lower()
    if any(
        x in texto_total_n
        for x in ["sem estoque", "indisponível", "indisponivel", "esgotado", "zerado"]
    ):
        estoque = "0"

    descricao_detalhada = (
        json_ld_data.get("descricao_detalhada", "")
        or texto_por_selectors(
            soup,
            [
                ".product-description",
                ".woocommerce-product-details__short-description",
                "[class*='description']",
                "meta[name='description']",
            ],
        )
    )
    descricao_detalhada = descricao_detalhada_valida(descricao_detalhada, titulo)

    url_imagens = normalizar_imagens("|".join(imagens[:12]))

    return {
        "url_produto": url_produto,
        "codigo": codigo,
        "descricao": safe_str(titulo),
        "descricao_detalhada": descricao_detalhada,
        "categoria": safe_str(categoria),
        "gtin": gtin,
        "ncm": ncm,
        "preco": preco,
        "quantidade": estoque,
        "url_imagens": url_imagens,
        "fonte_extracao": json_ld_data.get("fonte_extracao", "heuristica"),
    }
