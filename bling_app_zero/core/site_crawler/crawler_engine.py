# bling_app_zero/core/site_crawler/crawler_engine.py

from __future__ import annotations

from collections import deque
from typing import Dict, List, Set

import requests

from .crawler_dispatcher import fetch_html
from .link_discovery import (
    extract_category_links,
    extract_pagination_links,
    extract_product_links,
)
from .sitemap_engine import discover_links_from_sitemap
from bling_app_zero.core.site_crawler_extractors import extrair_detalhes_heuristicos


MAX_URLS = 300
MAX_PRODUCTS = 200
MAX_DEPTH = 2
MAX_PAGES_PER_CATEGORY = 5


def _dedupe_products(produtos: List[Dict]) -> List[Dict]:
    """Remove produtos duplicados preservando a ordem de descoberta."""
    vistos: Set[str] = set()
    saida: List[Dict] = []

    for produto in produtos:
        url = str(
            produto.get("url_produto")
            or produto.get("url")
            or produto.get("link")
            or ""
        ).strip()

        if not url or url in vistos:
            continue

        vistos.add(url)
        saida.append(produto)

    return saida


def _extrair_produto_completo(session: requests.Session, url_produto: str) -> Dict:
    """
    Entra na página real do produto e extrai os dados completos.

    Antes este crawler novo salvava apenas {"url": p}. Por isso o link externo
    aparecia no preview, mas o link da imagem vinha vazio: a imagem normalmente
    está dentro da página do produto, no JSON-LD, meta tags ou tags <img>.
    """
    url_produto = str(url_produto or "").strip()
    if not url_produto:
        return {}

    html_produto = fetch_html(session, url_produto)

    if not html_produto:
        return {
            "url": url_produto,
            "url_produto": url_produto,
            "link_externo": url_produto,
            "fonte_extracao": "link_sem_html",
        }

    try:
        detalhes = extrair_detalhes_heuristicos(url_produto, html_produto) or {}
    except Exception:
        detalhes = {}

    detalhes["url"] = detalhes.get("url") or url_produto
    detalhes["url_produto"] = detalhes.get("url_produto") or url_produto
    detalhes["link_externo"] = detalhes.get("link_externo") or url_produto

    return detalhes


def crawl_site(url: str) -> List[Dict]:
    session = requests.Session()

    visited: Set[str] = set()
    product_urls_seen: Set[str] = set()
    products: List[Dict] = []

    queue = deque([(url, 0)])
    category_page_count: Dict[str, int] = {}

    # 🔥 STEP 1 — sitemap
    sitemap_urls = discover_links_from_sitemap(session, url)

    for u in sitemap_urls[:50]:
        queue.append((u, 0))

    # 🔥 LOOP CONTROLADO
    while queue:
        if len(visited) >= MAX_URLS:
            break

        if len(products) >= MAX_PRODUCTS:
            break

        current_url, depth = queue.popleft()

        if current_url in visited:
            continue

        if depth > MAX_DEPTH:
            continue

        visited.add(current_url)

        html = fetch_html(session, current_url)

        if not html:
            continue

        # -------------------------
        # 🔥 PRODUTOS
        # -------------------------
        product_links = extract_product_links(html, current_url)

        for p in product_links:
            if not p or p in product_urls_seen:
                continue

            product_urls_seen.add(p)

            produto = _extrair_produto_completo(session, p)
            if produto:
                products.append(produto)

            if len(products) >= MAX_PRODUCTS:
                break

        # -------------------------
        # 🔥 CATEGORIAS
        # -------------------------
        category_links = extract_category_links(html, current_url)

        for c in category_links:
            if c not in visited:
                queue.append((c, depth + 1))

        # -------------------------
        # 🔥 PAGINAÇÃO (ANTI LOOP)
        # -------------------------
        pagination_links = extract_pagination_links(html, current_url)

        base_category = current_url.split("?")[0]

        count = category_page_count.get(base_category, 0)

        for p in pagination_links:
            if count >= MAX_PAGES_PER_CATEGORY:
                break

            if p not in visited:
                queue.append((p, depth + 1))
                count += 1

        category_page_count[base_category] = count

    return _dedupe_products(products)
