from __future__ import annotations

from typing import List
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .config import BLOCKED_URL_PARTS, PRODUCT_HINTS, CATEGORY_HINTS
from .utils import normalize_url, same_domain


def is_blocked_url(url: str) -> bool:
    low = url.lower()
    return any(part in low for part in BLOCKED_URL_PARTS)


def looks_like_product_url(url: str) -> bool:
    low = url.lower()
    return any(hint in low for hint in PRODUCT_HINTS)


def looks_like_category_url(url: str) -> bool:
    low = url.lower()
    return any(hint in low for hint in CATEGORY_HINTS)


def extract_links(html: str, base_url: str, base_domain: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []

    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        if not href:
            continue

        absolute = normalize_url(urljoin(base_url, href))

        if not absolute.startswith("http"):
            continue

        if not same_domain(absolute, base_domain):
            continue

        if is_blocked_url(absolute):
            continue

        if looks_like_product_url(absolute) or looks_like_category_url(absolute):
            links.append(absolute)

    return list(dict.fromkeys(links))
