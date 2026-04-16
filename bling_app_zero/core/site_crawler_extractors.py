
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
        safe
