from __future__ import annotations

"""Extrator seguro de imagens para produtos.

Objetivo: retornar somente imagens reais, nunca link de página de produto.
Saída: URLs separadas por `|` para a coluna `URL Imagens Externas`.
"""

import json
import re
from html import unescape
from typing import Iterable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".avif")
BAD = (
    "logo", "sprite", "placeholder", "favicon", "pixel", "analytics",
    "base64", "whatsapp", "instagram", "facebook.com/tr", "doubleclick",
    "blank", "loading", "spacer", "transparent", "svg+xml",
)
GOOD_HINTS = ("image", "imagem", "foto", "media", "cdn", "upload", "storage", "files", "catalog")
ATTRS = (
    "content", "src", "data-src", "data-original", "data-zoom-image",
    "data-large_image", "data-large-image", "data-lazy", "data-lazy-src",
    "srcset", "data-srcset", "href", "style",
)
SELECTORS = (
    "meta[property='og:image']", "meta[property='og:image:secure_url']",
    "meta[name='twitter:image']", "meta[itemprop='image']", "[itemprop='image']",
    "img", "source", "a[href]", "[style]",
)
URL_TOKEN = re.compile(r"(?:https?:)?//[^\s\"'<>]+|[^\s\"'<>]+\.(?:jpg|jpeg|png|webp|avif)(?:\?[^\s\"'<>]*)?", re.I)


def _txt(value: object) -> str:
    return unescape(str(value or "")).strip().replace("\\/", "/")


def _add(out: list[str], value: object) -> None:
    raw = _txt(value)
    if not raw:
        return
    for part in raw.split(","):
        token = part.strip().split(" ")[0]
        if token:
            out.append(token)
    out.extend(URL_TOKEN.findall(raw))


def _abs(page_url: str, value: object) -> str:
    raw = _txt(value).strip().strip('"\'[]{}()')
    if raw.startswith("//"):
        raw = "https:" + raw
    return urljoin(page_url, raw)


def _is_product_page(url: str) -> bool:
    path = urlparse(url).path.lower()
    return "/produto/" in path and not any(ext in path for ext in IMG_EXT)


def _valid(url: str) -> bool:
    low = str(url or "").lower()
    if not low.startswith(("http://", "https://")):
        return False
    if _is_product_page(low):
        return False
    if any(x in low for x in BAD):
        return False
    if any(ext in low for ext in IMG_EXT):
        return True
    return any(x in low for x in GOOD_HINTS)


def _json_payloads(soup: BeautifulSoup) -> list[object]:
    items: list[object] = []
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            items.append(json.loads(raw))
        except Exception:
            continue
    return items


def _walk_images(obj: object) -> Iterable[object]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in {"image", "images", "thumbnail", "thumbnailurl", "contenturl"}:
                if isinstance(value, list):
                    for item in value:
                        yield item
                else:
                    yield value
            if isinstance(value, (dict, list)):
                yield from _walk_images(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_images(item)


def extract_safe_product_images(page_url: str, html: str, extra_candidates: Iterable[object] | None = None, max_images: int = 20) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    candidates: list[str] = []

    for item in extra_candidates or []:
        _add(candidates, item)

    for payload in _json_payloads(soup):
        for item in _walk_images(payload):
            _add(candidates, item)

    for selector in SELECTORS:
        for tag in soup.select(selector):
            for attr in ATTRS:
                value = tag.get(attr)
                if value:
                    _add(candidates, value)

    for script in soup.select("script"):
        raw = script.string or script.get_text(" ", strip=True)
        if raw and any(ext[1:] in raw.lower() for ext in IMG_EXT):
            _add(candidates, raw)

    result: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        url = _abs(page_url, item)
        if not _valid(url) or url in seen:
            continue
        seen.add(url)
        result.append(url)
        if len(result) >= max_images:
            break
    return "|".join(result)
