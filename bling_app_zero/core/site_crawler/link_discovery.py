from __future__ import annotations

import re
from typing import List
from urllib.parse import urljoin, urlparse, urlunparse, parse_qsl, urlencode

from bs4 import BeautifulSoup


def _clean_url(url: str) -> str:
    url = str(url or "").strip()
    if not url:
        return ""

    parsed = urlparse(url)
    query = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if not k.lower().startswith(("utm_", "fbclid", "gclid"))
    ]

    parsed = parsed._replace(
        fragment="",
        query=urlencode(query),
    )

    return urlunparse(parsed)


def _same_domain(url: str, base: str) -> bool:
    try:
        return urlparse(url).netloc.lower() == urlparse(base).netloc.lower()
    except Exception:
        return False


def _dedupe(items: List[str]) -> List[str]:
    out = []
    seen = set()

    for item in items:
        item = _clean_url(item)
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)

    return out


def _hrefs(html: str, base: str) -> List[str]:
    soup = BeautifulSoup(html or "", "lxml")
    links = []

    for a in soup.find_all("a", href=True):
        href = urljoin(base, a.get("href", ""))
        href = _clean_url(href)

        if not href:
            continue

        if not href.startswith(("http://", "https://")):
            continue

        if not _same_domain(href, base):
            continue

        links.append(href)

    return _dedupe(links)


def _is_product_link(url: str) -> bool:
    u = url.lower()

    pistas = [
        "/produto",
        "/produtos",
        "/product",
        "/products",
        "/p/",
        "/item/",
        "produto=",
        "product_id=",
        "sku=",
    ]

    if any(p in u for p in pistas):
        return True

    if re.search(r"/[a-z0-9-]+-\d{3,}($|[/?])", u):
        return True

    return False


def _is_category_link(url: str) -> bool:
    u = url.lower()

    bloqueios = [
        "/login",
        "/conta",
        "/account",
        "/checkout",
        "/carrinho",
        "/cart",
        "/politica",
        "/termos",
        "/wishlist",
        "/favoritos",
        "whatsapp",
        "instagram",
        "facebook",
        "youtube",
    ]

    if any(b in u for b in bloqueios):
        return False

    pistas = [
        "/categoria",
        "/categorias",
        "/category",
        "/collections",
        "/departamento",
        "/departamentos",
        "/loja",
        "/shop",
        "/marcas",
        "/brand",
    ]

    return any(p in u for p in pistas)


def _is_pagination_link(url: str) -> bool:
    u = url.lower()
    return bool(
        re.search(r"([?&]page=\d+)", u)
        or re.search(r"([?&]p=\d+)", u)
        or re.search(r"/page/\d+", u)
        or re.search(r"/pagina/\d+", u)
    )


def extract_product_links(html, base):
    return [u for u in _hrefs(html, base) if _is_product_link(u)]


def extract_category_links(html, base):
    return [u for u in _hrefs(html, base) if _is_category_link(u)]


def extract_pagination_links(html, base):
    links = [u for u in _hrefs(html, base) if _is_pagination_link(u)]

    soup = BeautifulSoup(html or "", "lxml")
    for a in soup.find_all("a", href=True):
        texto = a.get_text(" ", strip=True).lower()
        if texto in {"próximo", "proximo", "next", ">", "»"}:
            links.append(urljoin(base, a["href"]))

    return _dedupe(links)
