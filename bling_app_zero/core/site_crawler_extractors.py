from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

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


# ============================================================
# HELPERS BASE
# ============================================================

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


# ============================================================
# JSON-LD (MAIS FORTE)
# ============================================================

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

    marca = ""
    brand = prod.get("brand")
    if isinstance(brand, dict):
        marca = safe_str(brand.get("name"))
    elif isinstance(brand, str):
        marca = brand

    categoria = safe_str(prod.get("category"))
    descricao = safe_str(prod.get("description"))

    imagens = prod.get("image", [])
    if isinstance(imagens, str):
        imagens = [imagens]

    imagens = [
        urljoin(url_produto, safe_str(img))
        for img in imagens
        if safe_str(img) and imagem_valida(urljoin(url_produto, safe_str(img)))
    ]

    preco = ""
    quantidade = ""

    offers = prod.get("offers")
    if isinstance(offers, dict):
        preco = safe_str(offers.get("price"))
        disponibilidade = normalizar_texto(offers.get("availability"))

        if "outofstock" in disponibilidade:
            quantidade = "0"
        else:
            quantidade = "1"

    return {
        "codigo": sku,
        "descricao": nome,
        "descricao_detalhada": descricao,
        "descricao_curta": nome[:120] if nome else "",
        "categoria": categoria,
        "marca": marca,
        "gtin": gtin,
        "preco": normalizar_preco_para_planilha(preco),
        "quantidade": quantidade,
        "url_imagens": normalizar_imagens("|".join(imagens[:12])),
        "fonte_extracao": "json_ld",
    }


# ============================================================
# HEURÍSTICA FORTE
# ============================================================

def extrair_marca(texto: str, soup: BeautifulSoup) -> str:
    marca = texto_por_selectors(soup, [
        "meta[property='og:brand']",
        "meta[name='brand']"
    ])

    if marca:
        return marca

    match = re.search(r"(?:marca|brand)[\s:\-]*([A-Za-z0-9 ]+)", texto, re.I)
    if match:
        return safe_str(match.group(1))

    return ""


def extrair_quantidade(texto: str) -> str:
    texto_n = texto.lower()

    if any(x in texto_n for x in ["sem estoque", "indisponível", "esgotado"]):
        return "0"

    if any(x in texto_n for x in ["em estoque", "disponível"]):
        return "1"

    return ""


def extrair_breadcrumb(soup: BeautifulSoup) -> str:
    breadcrumb = []

    for el in soup.select("nav a, .breadcrumb a, [class*=breadcrumb] a"):
        txt = safe_str(el.get_text(" ", strip=True))
        if txt and txt.lower() not in {"home", "inicio"}:
            breadcrumb.append(txt)

    return " > ".join(dict.fromkeys(breadcrumb))


# ============================================================
# EXTRAÇÃO PRINCIPAL
# ============================================================

def extrair_detalhes_heuristicos(url_produto: str, html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    json_ld = extrair_produto_json_ld(soup, url_produto)

    titulo = texto_por_selectors(soup, [
        "h1",
        ".product-title",
        "[itemprop='name']",
        "meta[property='og:title']",
        "title",
    ]) or json_ld.get("descricao", "")

    texto_total = soup.get_text(" ", strip=True)

    preco = texto_por_selectors(soup, ["[class*=price]"])
    if not preco:
        preco = extrair_preco(texto_total)

    preco = normalizar_preco_para_planilha(preco)

    imagens = imagens_por_selectors(url_produto, soup, ["img"])

    if not imagens and json_ld.get("url_imagens"):
        imagens = json_ld["url_imagens"].split("|")

    marca = extrair_marca(texto_total, soup) or json_ld.get("marca", "")

    quantidade = extrair_quantidade(texto_total) or json_ld.get("quantidade", "1")

    descricao_detalhada = (
        json_ld.get("descricao_detalhada", "")
        or texto_por_selectors(soup, ["[class*=description]", "meta[name='description']"])
    )

    descricao_detalhada = descricao_detalhada_valida(descricao_detalhada, titulo)

    categoria = extrair_breadcrumb(soup) or json_ld.get("categoria", "")

    return {
        "url_produto": url_produto,
        "codigo": json_ld.get("codigo", ""),
        "descricao": titulo,
        "descricao_curta": titulo[:120],
        "descricao_detalhada": descricao_detalhada,
        "categoria": categoria,
        "marca": marca,
        "gtin": json_ld.get("gtin", ""),
        "preco": preco,
        "quantidade": quantidade or "1",
        "url_imagens": normalizar_imagens("|".join(imagens[:10])),
        "fonte_extracao": json_ld.get("fonte_extracao", "heuristica"),
    }
    
