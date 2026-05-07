from __future__ import annotations

"""Extrator seguro de imagens para produtos.

Objetivo: retornar somente imagens reais, nunca link de página, logo, banner,
pixel, rede social, ícone, pagamento ou qualquer URL de rastreamento.
Saída: URLs separadas por `|` para a coluna `URL Imagens Externas`.
"""

import json
import re
from html import unescape
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from bling_app_zero.core.image_quality_validator import filter_product_image_urls

IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".avif")
ATTRS = (
    "content", "src", "data-src", "data-original", "data-zoom-image", "data-large_image", "data-large-image",
    "data-lazy", "data-lazy-src", "srcset", "data-srcset", "href", "style", "alt", "title",
)
SELECTORS = (
    "meta[property='og:image']", "meta[property='og:image:secure_url']", "meta[name='twitter:image']",
    "meta[itemprop='image']", "[itemprop='image']", "img", "source", "a[href]", "[style]",
)
URL_TOKEN = re.compile(r"(?:https?:)?//[^\s\"'<>]+|[^\s\"'<>]+\.(?:jpg|jpeg|png|webp|avif)(?:\?[^\s\"'<>]*)?", re.I)
TITLE_SELECTORS = (
    "h1", "meta[property='og:title']", "meta[name='twitter:title']", "meta[itemprop='name']", "[itemprop='name']",
)


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


def _json_payloads(soup: BeautifulSoup) -> list[object]:
    items: list[object] = []
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                items.extend(parsed)
            else:
                items.append(parsed)
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


def _walk_names(obj: object) -> Iterable[str]:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in {"name", "headline", "title", "description", "sku", "mpn", "gtin", "gtin13"}:
                if isinstance(value, (str, int, float)):
                    yield str(value)
            if isinstance(value, (dict, list)):
                yield from _walk_names(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_names(item)


def _page_title_context(soup: BeautifulSoup) -> str:
    parts: list[str] = []
    for selector in TITLE_SELECTORS:
        for tag in soup.select(selector):
            if tag.name == "meta":
                parts.append(_txt(tag.get("content")))
            else:
                parts.append(_txt(tag.get_text(" ", strip=True)))
    if soup.title:
        parts.append(_txt(soup.title.get_text(" ", strip=True)))
    return " ".join(part for part in parts if part)


def extract_safe_product_images(
    page_url: str,
    html: str,
    extra_candidates: Iterable[object] | None = None,
    max_images: int = 12,
    product_title: str = "",
    validate_remote: bool = False,
) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    candidates: list[str] = []
    context_parts: list[str] = []

    for item in extra_candidates or []:
        _add(candidates, item)

    for payload in _json_payloads(soup):
        for item in _walk_images(payload):
            _add(candidates, item)
        context_parts.extend(_walk_names(payload))

    context_parts.append(_page_title_context(soup))

    for selector in SELECTORS:
        for tag in soup.select(selector):
            local_context = " ".join(_txt(tag.get(attr)) for attr in ("alt", "title", "aria-label") if tag.get(attr))
            if local_context:
                context_parts.append(local_context)
            for attr in ATTRS:
                value = tag.get(attr)
                if value:
                    _add(candidates, value)

    for script in soup.select("script"):
        raw = script.string or script.get_text(" ", strip=True)
        if raw and any(ext[1:] in raw.lower() for ext in IMG_EXT):
            _add(candidates, raw)

    absolute_candidates = [_abs(page_url, item) for item in candidates]
    title = product_title or _page_title_context(soup)
    context = " ".join(context_parts)
    return filter_product_image_urls(
        absolute_candidates,
        product_title=title,
        context=context,
        max_images=max_images,
        require_remote=validate_remote,
        require_product_match=False,
    )
