from __future__ import annotations

"""Descoberta de URLs de produto via sitemap.

Regra do fluxo:
- Sitemap serve para enriquecer a descoberta de páginas de produto.
- O sistema deve entrar em cada sitemap encontrado, inclusive sitemap index,
  sub-sitemaps e arquivos .xml/.xml.gz.
- O sitemap NÃO cria dados de produto; ele só alimenta a lista de URLs
  `/produto/...` que depois serão visitadas página por página.
"""

import gzip
import re
import xml.etree.ElementTree as ET
from collections import deque
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests


PRODUCT_URL_RE = re.compile(r"/produto/", re.IGNORECASE)
SITEMAP_HINT_RE = re.compile(r"(?:sitemap|\.xml(?:\.gz)?$)", re.IGNORECASE)
SITEMAP_LIMIT = 500


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


def _initial_sitemaps(seed_urls: Iterable[str]) -> list[str]:
    roots: list[str] = []
    seen_roots: set[str] = set()
    for seed in seed_urls:
        root = _root_url(str(seed))
        if root and root not in seen_roots:
            seen_roots.add(root)
            roots.append(root)

    result: list[str] = []
    seen: set[str] = set()
    for root in roots:
        for candidate in (
            urljoin(root, "sitemap.xml"),
            urljoin(root, "sitemap_index.xml"),
            urljoin(root, "sitemap-products.xml"),
            urljoin(root, "sitemap_produtos.xml"),
            urljoin(root, "sitemap-product.xml"),
            urljoin(root, "sitemap_produto.xml"),
        ):
            if candidate not in seen:
                seen.add(candidate)
                result.append(candidate)
    return result


def _looks_like_sitemap(url: str) -> bool:
    return bool(SITEMAP_HINT_RE.search(str(url or "")))


def _clean_url(url: str) -> str:
    return str(url or "").strip().split("#", 1)[0].split("?", 1)[0]


def discover_sitemap_urls(seed_urls: Iterable[str], *, max_sitemaps: int = SITEMAP_LIMIT) -> list[str]:
    """Descobre sitemaps recursivamente.

    Usa uma fila: baixa cada sitemap, coleta todos os <loc>, adiciona novos
    sitemaps encontrados de volta na fila e segue até o limite interno.
    """
    queue: deque[str] = deque(_initial_sitemaps(seed_urls))
    visited: set[str] = set()
    discovered: list[str] = []

    while queue and len(discovered) < max_sitemaps:
        sitemap = _clean_url(queue.popleft())
        if not sitemap or sitemap in visited:
            continue
        visited.add(sitemap)
        discovered.append(sitemap)

        try:
            locs = _xml_locs(_download_text(sitemap))
        except Exception:
            continue

        for loc in locs:
            clean = _clean_url(loc)
            if not clean or clean in visited:
                continue
            if _looks_like_sitemap(clean) and len(discovered) + len(queue) < max_sitemaps:
                queue.append(clean)

    return discovered


def discover_product_urls_from_sitemaps(seed_urls: Iterable[str], *, max_products: int = 5000) -> list[str]:
    """Entra em cada sitemap descoberto e retorna URLs de produto."""
    product_urls: list[str] = []
    seen_products: set[str] = set()

    for sitemap_url in discover_sitemap_urls(seed_urls):
        try:
            locs = _xml_locs(_download_text(sitemap_url))
        except Exception:
            continue

        for loc in locs:
            clean = _clean_url(loc)
            if not clean or not PRODUCT_URL_RE.search(clean):
                continue
            if clean in seen_products:
                continue
            seen_products.add(clean)
            product_urls.append(clean)
            if len(product_urls) >= max_products:
                return product_urls

    return product_urls
