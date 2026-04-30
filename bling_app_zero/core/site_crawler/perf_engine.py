from __future__ import annotations

import time
from collections import deque
from typing import Callable, Dict, List, Optional
from urllib.parse import urlparse

import pandas as pd

from .config import CrawlConfig
from .product_page_extractor import extract_product_from_html
from .http_fetcher import fetch_html
from .link_extractor import extract_links, is_blocked_url
from .utils import normalize_url


def crawl_site_perf(
    start_url: str,
    config: Optional[CrawlConfig] = None,
    progress_callback: Optional[Callable[[int, str, int], None]] = None,
) -> pd.DataFrame:
    config = config or CrawlConfig()
    start_url = normalize_url(start_url)
    parsed = urlparse(start_url)
    base_domain = parsed.netloc.lower().replace("www.", "")

    queue = deque([(start_url, 0)])
    visited: set[str] = set()
    enqueued: set[str] = {start_url}
    products: List[Dict[str, str]] = []
    product_urls: set[str] = set()
    started_at = time.time()

    while queue:
        if time.time() - started_at > int(getattr(config, "max_seconds", 180)):
            break
        if len(visited) >= int(config.max_urls):
            break
        if len(products) >= int(config.max_products):
            break

        current_url, depth = queue.popleft()
        current_url = normalize_url(current_url)

        if current_url in visited:
            continue
        if is_blocked_url(current_url):
            continue
        if depth > int(config.max_depth):
            continue

        visited.add(current_url)

        html = fetch_html(current_url, timeout=int(config.timeout))
        if not html:
            continue

        product = extract_product_from_html(current_url, html)
        if product and current_url not in product_urls:
            products.append(product)
            product_urls.add(current_url)
            continue

        links = extract_links(html, current_url, base_domain)
        max_queue_size = int(getattr(config, "max_queue_size", 1500))
        for link in links:
            link = normalize_url(link)
            if link in visited or link in enqueued:
                continue
            if len(enqueued) >= max_queue_size:
                break
            queue.append((link, depth + 1))
            enqueued.add(link)

        sleep_seconds = float(getattr(config, "sleep_seconds", 0) or 0)
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    return pd.DataFrame(products)


def buscar_produtos_site_perf(url: str) -> pd.DataFrame:
    return crawl_site_perf(url)
