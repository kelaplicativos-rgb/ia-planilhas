from __future__ import annotations

import re
from collections import deque
from html import unescape
from typing import Iterable, Optional
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

PRODUCT_RE = re.compile(r"/produto/", re.I)
PAGE_KEYS = ("page", "pagina", "p", "pg")
BAD_HINTS = ("/login", "/conta", "/checkout", "/carrinho", "/cart", "whatsapp", "facebook", "instagram")
MAX_EMPTY = 5
MAX_PAGES = 500


def _headers() -> dict[str, str]:
    return {"User-Agent": "Mozilla/5.0 AppleWebKit/537.36 Chrome/124 Safari/537.36", "Accept-Language": "pt-BR,pt;q=0.9"}


def _get(url: str) -> str:
    response = requests.get(url, headers=_headers(), timeout=20)
    response.raise_for_status()
    return response.text or ""


def _abs(base: str, href: object) -> str:
    raw = unescape(str(href or "")).strip()
    if raw.startswith("//"):
        raw = "https:" + raw
    return urljoin(base, raw).split("#")[0]


def _host(url: str) -> str:
    return urlparse(str(url or "")).netloc.lower()


def _same_host(url: str, hosts: set[str]) -> bool:
    return not hosts or _host(url) in hosts


def _is_product(url: str) -> bool:
    parsed = urlparse(str(url or ""))
    return bool(parsed.scheme and parsed.netloc and PRODUCT_RE.search(parsed.path))


def _clean_product(url: str) -> str:
    parsed = urlparse(str(url or ""))
    return parsed._replace(query="", fragment="").geturl()


def _is_listing(url: str, hosts: set[str]) -> bool:
    if not _same_host(url, hosts) or _is_product(url):
        return False
    low = url.lower()
    return not any(bad in low for bad in BAD_HINTS)


def _query_pages(url: str, page: int) -> list[str]:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    existing = [key for key in query if key.lower() in PAGE_KEYS]
    result: list[str] = []
    if existing:
        for key in existing:
            new_query = dict(query)
            new_query[key] = str(page)
            result.append(urlunparse(parsed._replace(query=urlencode(new_query))))
    else:
        for key in ("page", "pagina"):
            new_query = dict(query)
            new_query[key] = str(page)
            result.append(urlunparse(parsed._replace(query=urlencode(new_query))))
    return result


def _path_pages(url: str, page: int) -> list[str]:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if not path:
        return []
    if re.search(r"/page/\d+$", path, re.I):
        return [urlunparse(parsed._replace(path=re.sub(r"/page/\d+$", f"/page/{page}", path, flags=re.I), query=""))]
    return [urlunparse(parsed._replace(path=f"{path}/page/{page}", query=""))]


def _pagination_links(soup: BeautifulSoup, current_url: str, hosts: set[str]) -> list[str]:
    selectors = ("a[rel='next']", ".pagination a[href]", "[class*='pagination'] a[href]", "[class*='paginacao'] a[href]", "a[href*='page=']", "a[href*='pagina=']", "a[href*='/page/']")
    out: list[str] = []
    seen: set[str] = set()
    for selector in selectors:
        for anchor in soup.select(selector):
            href = _abs(current_url, anchor.get("href", ""))
            if href and href not in seen and _is_listing(href, hosts):
                seen.add(href)
                out.append(href)
    return out


def discover_product_urls_infinity(seed_urls: Iterable[str], *, max_products: Optional[int] = None) -> list[str]:
    seeds = [str(url or "").strip() for url in seed_urls if str(url or "").strip()]
    hosts = {_host(url) for url in seeds if _host(url)}
    limit = int(max_products or 5000)
    products: list[str] = []
    seen_products: set[str] = set()
    queue: deque[tuple[str, int]] = deque()
    seen_pages: set[str] = set()
    empty_count = 0

    def add_product(url: str) -> bool:
        clean = _clean_product(_abs(url, url))
        if not _is_product(clean) or not _same_host(clean, hosts) or clean in seen_products:
            return False
        seen_products.add(clean)
        products.append(clean)
        return len(products) >= limit

    for seed in seeds:
        if add_product(seed):
            return products
        if _is_listing(seed, hosts):
            queue.append((seed, 1))

    while queue and len(seen_pages) < MAX_PAGES and len(products) < limit:
        page_url, page_num = queue.popleft()
        if page_url in seen_pages:
            continue
        seen_pages.add(page_url)
        before = len(products)
        try:
            soup = BeautifulSoup(_get(page_url), "html.parser")
        except Exception:
            empty_count += 1
            if empty_count >= MAX_EMPTY:
                break
            continue
        for anchor in soup.select("a[href]"):
            if add_product(_abs(page_url, anchor.get("href", ""))):
                return products
        added = len(products) - before
        empty_count = empty_count + 1 if added == 0 else 0
        if empty_count >= MAX_EMPTY:
            break
        candidates: list[str] = []
        candidates.extend(_pagination_links(soup, page_url, hosts))
        candidates.extend(_query_pages(page_url, page_num + 1))
        candidates.extend(_path_pages(page_url, page_num + 1))
        for candidate in candidates:
            if candidate not in seen_pages and _is_listing(candidate, hosts):
                queue.append((candidate, page_num + 1))
    return products[:limit]
