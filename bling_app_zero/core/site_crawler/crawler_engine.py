from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from .http_client import build_session
from .sitemap_engine import discover_links_from_sitemap
from .link_discovery import (
    extract_product_links,
    extract_category_links,
    extract_pagination_links,
)
from .product_extractor import extract_product_from_page
from .product_normalizer import normalize_products, to_dataframe
from .crawler_utils import log


def run_crawler(
    url: str,
    *,
    auth_context: Optional[Dict] = None,
    varrer_site_completo: bool = True,
    sitemap_completo: bool = True,
    max_workers: int = 8,
) -> pd.DataFrame:

    session = build_session(auth_context)

    log(f"[ENGINE] iniciando crawler → {url}")

    product_links: List[str] = []
    pages_to_visit: List[str] = [url]

    # =========================
    # SITEMAP
    # =========================
    if sitemap_completo:
        sitemap_links = discover_links_from_sitemap(session, url)

        for link in sitemap_links:
            if "/produto" in link or "/p/" in link:
                product_links.append(link)
            else:
                pages_to_visit.append(link)

        log(f"[ENGINE] sitemap → {len(sitemap_links)} links")

    # =========================
    # VARREDURA
    # =========================
    visited = set()

    while pages_to_visit:
        page = pages_to_visit.pop(0)

        if page in visited:
            continue

        visited.add(page)

        html = session.get(page, timeout=20, verify=False).text

        product_links += extract_product_links(html, page)
        pages_to_visit += extract_category_links(html, page)
        pages_to_visit += extract_pagination_links(html, page)

        if not varrer_site_completo and len(product_links) > 200:
            break

    product_links = list(set(product_links))

    log(f"[ENGINE] produtos encontrados → {len(product_links)} links")

    # =========================
    # EXTRAÇÃO
    # =========================
    produtos: List[Dict] = []

    for i, link in enumerate(product_links):
        try:
            html = session.get(link, timeout=20, verify=False).text
            produto = extract_product_from_page(html, link)

            if produto:
                produtos.append(produto)

        except Exception as e:
            log(f"[ERRO PRODUTO] {link} → {e}")

        if i % 20 == 0:
            log(f"[ENGINE] processados {i}/{len(product_links)}")

    produtos = normalize_products(produtos)

    return to_dataframe(produtos)
