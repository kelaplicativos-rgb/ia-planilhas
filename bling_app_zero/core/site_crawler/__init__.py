from __future__ import annotations

from .config import CrawlConfig
from .engine import buscar_produtos_site, crawl_site
from .http_fetcher import fetch_html
from .link_extractor import extract_links, is_blocked_url, looks_like_category_url, looks_like_product_url
from .utils import normalize_url, same_domain

__all__ = [
    "CrawlConfig",
    "buscar_produtos_site",
    "crawl_site",
    "fetch_html",
    "extract_links",
    "is_blocked_url",
    "looks_like_category_url",
    "looks_like_product_url",
    "normalize_url",
    "same_domain",
]
