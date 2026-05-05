from __future__ import annotations

"""Descoberta opcional de URLs de produto via sitemap.

O sitemap complementa a varredura Flash Amplo quando a listagem/categoria não
mostra todos os links. Ele NÃO inventa dados de produto; apenas alimenta a lista
de páginas `/produto/...` que depois serão visitadas uma a uma.
"""

import gzip
import re
import xml.etree.ElementTree as ET
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests


PRODUCT_URL_RE = re.compile(r"/produto/", re.IGNORECASE)
SITEMAP_LIMIT = 50


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0 Safari/537.36",
        "Accept": "application/xml,text/xml,text/plain,*/*",
    }


def _root_url(url: str) -> str:
    parsed = urlparse(str(url or ""))
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}/"


def _download_text(url: str, timeout: int = 20) -> str:
    response = requests.get(url, headers=_headers(), timeout=timeout)
    response.raise_for_status()
    content = response.content or b""
    if url.lower().endswith(".gz"):
        content = gzip.decompress(content)
    return content.decode(response.encoding or "utf-8", errors="ignore")


def _xml_locs(xml_text: str) -> list[str]:
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except Exception:
        return [m.strip() for m in re.findall(r"<loc>(.*?)</loc>", xml_text, flags=re.IGNORECASE | re.DOTALL)]

    locs: list[str] = []
    for elem in root.iter():
        if elem.tag.lower().endswith("loc") and elem.text:
            locs.append(elem.text.strip())
    return locs


def discover_sitemap_urls(seed_urls: Iterable[str], *, max_sitemaps: int = SITEMAP_LIMIT) -> list[str]:
    roots: list[str] = []
    seen_roots: set[str] = set()
    for seed in seed_urls:
        root = _root_url(str(seed))
        if root and root not in seen_roots:
            seen_roots.add(root)
            roots.append(root)

    sitemap_urls: list[str] = []
    seen: set[str] = set()
    for root in roots:
        for candidate in (
            urljoin(root, "sitemap.xml"),
            urljoin(root, "sitemap_index.xml"),
            urljoin(root, "sitemap-products.xml"),
            urljoin(root, "sitemap_produtos.xml"),
        ):
            if candidate not in seen:
                seen.add(candidate)
                sitemap_urls.append(candidate)

    expanded: list[str] = []
    seen_expanded: set[str] = set(sitemap_urls)
    for sitemap in sitemap_urls[:max_sitemaps]:
        try:
            locs = _xml_locs(_download_text(sitemap))
        except Exception:
            continue
        for loc in locs:
            low = loc.lower()
            if ("sitemap" in low or low.endswith(".xml") or low.endswith(".xml.gz")) and loc not in seen_expanded:
                seen_expanded.add(loc)
                expanded.append(loc)
                if len(sitemap_urls) + len(expanded) >= max_sitemaps:
                    break

    return sitemap_urls + expanded


def discover_product_urls_from_sitemaps(seed_urls: Iterable[str], *, max_products: int = 500) -> list[str]:
    product_urls: list[str] = []
    seen: set[str] = set()
    for sitemap_url in discover_sitemap_urls(seed_urls):
        try:
            locs = _xml_locs(_download_text(sitemap_url))
        except Exception:
            continue
        for loc in locs:
            loc = str(loc or "").strip()
            if not loc or not PRODUCT_URL_RE.search(loc):
                continue
            clean = loc.split("#", 1)[0].split("?", 1)[0]
            if clean in seen:
                continue
            seen.add(clean)
            product_urls.append(clean)
            if len(product_urls) >= max_products:
                return product_urls
    return product_urls
