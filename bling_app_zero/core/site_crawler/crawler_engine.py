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


MAX_URLS = 300
MAX_PRODUCTS = 200
MAX_DEPTH = 2
MAX_PAGES_PER_CATEGORY = 5


def crawl_site(url: str) -> List[Dict]:
    session = requests.Session()

    visited: Set[str] = set()
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
            if p not in visited:
                products.append({"url": p})

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

    return products
