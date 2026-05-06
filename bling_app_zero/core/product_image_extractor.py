from __future__ import annotations

"""Extração única e robusta de imagens de páginas de produto.

Este módulo é o único responsável por transformar HTML + dados estruturados em
`URL Imagens Externas` no padrão do Bling, usando `|` como separador.
"""

import json
import re
from html import unescape
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

IMAGE_URL_RE = re.compile(
    r"(?:https?:)?//[^\s\"'<>\\]+|[^\s\"'<>\\]+\.(?:jpg|jpeg|png|webp|avif)(?:\?[^\s\"'<>\\]*)?",
    re.IGNORECASE,
)
IMAGE_EXT_RE = re.compile(r"\.(jpg|jpeg|png|webp|avif)(?:$|[?#])", re.IGNORECASE)
BAD_IMAGE_FRAGMENTS = (
    "logo",
    "sprite",
    "placeholder",
    "blank",
    "loading",
    "favicon",
    "facebook.com/tr",
    "pixel",
    "analytics",
    "doubleclick",
    "whatsapp",
    "instagram",
    "svg+xml",
    "base64,",
    "transparent",
    "spacer",
    "banner",
    "icone",
    "/icon",
)
GOOD_IMAGE_HINTS = (
    "image",
    "imagem",
    "foto",
    "photos",
    "product",
    "produto",
    "upload",
    "cdn",
    "media",
    "catalog",
    "produto",
    "files",
)
IMAGE_ATTRS = (
    "content",
    "src",
    "data-src",
    "data-original",
    "data-zoom-image",
    "data-large_image",
    "data-large-image",
    "data-lazy",
    "data-lazy-src",
    "srcset",
    "data-srcset",
    "href",
    "style",
)
IMAGE_SELECTORS = (
    "meta[property='og:image']",
    "meta[property='og:image:secure_url']",
    "meta[name='twitter:image']",
    "meta[itemprop='image']",
    "[itemprop='image']",
    "img",
    "source",
    "a[href]",
    "[style]",
)


def _clean_raw(value: object) -> str:
    return unescape(str(value or "")).strip().replace("\\/", "/")


def _absolute_url(value: object, page_url: str) -> str:
    raw = _clean_raw(value).strip().strip('"\'[]{}()')
    if not raw:
        return ""
    if raw.startswith("//"):
        raw = "https:" + raw
    return urljoin(page_url, raw)


def _add_candidate(candidates: list[str], value: object) -> None:
    raw = _clean_raw(value)
    if not raw:
        return

    # srcset: pega cada URL antes do tamanho/resolução.
    if "," in raw:
        for part in raw.split(","):
            token = part.strip().split(" ")[0]
            if token:
                candidates.append(token)

    token = raw.strip().split(" ")[0]
    if token:
        candidates.append(token)

    for match in IMAGE_URL_RE.findall(raw):
        candidates.append(match)


def _json_ld_payloads(soup: BeautifulSoup) -> list[object]:
    payloads: list[object] = []
    for script in soup.select('script[type="application/ld+json"]'):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            payloads.append(json.loads(raw))
        except Exception:
            continue
    return payloads


def _walk_json_images(payload: object) -> Iterable[object]:
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_low = str(key).lower()
            if key_low in {"image", "images", "thumbnail", "thumbnailurl", "contenturl", "url"}:
                if isinstance(value, list):
                    for item in value:
                        yield item
                else:
                    yield value
            if isinstance(value, (dict, list)):
                yield from _walk_json_images(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _walk_json_images(item)


def _is_valid_image(url: str) -> bool:
    lower = str(url or "").lower()
    if not lower.startswith(("http://", "https://")):
        return False
    if any(fragment in lower for fragment in BAD_IMAGE_FRAGMENTS):
        return False
    if IMAGE_EXT_RE.search(lower):
        return True
    return any(hint in lower for hint in GOOD_IMAGE_HINTS)


def extract_product_images_from_html(page_url: str, html: str, extra_candidates: Iterable[object] | None = None, max_images: int = 20) -> str:
    """Retorna URLs de imagens separadas por `|`.

    A função varre JSON-LD, metatags, tags img/source/a, atributos lazy e scripts.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    candidates: list[str] = []

    for value in extra_candidates or []:
        _add_candidate(candidates, value)

    for payload in _json_ld_payloads(soup):
        for value in _walk_json_images(payload):
            _add_candidate(candidates, value)

    for selector in IMAGE_SELECTORS:
        for tag in soup.select(selector):
            for attr in IMAGE_ATTRS:
                value = tag.get(attr)
                if value:
                    _add_candidate(candidates, value)

    # Fallback bruto para galerias escondidas em scripts/estado JS.
    for script in soup.select("script"):
        text = script.string or script.get_text(" ", strip=True)
        if text and any(token in text.lower() for token in ("jpg", "jpeg", "png", "webp", "avif", "image", "imagem", "gallery", "galeria")):
            _add_candidate(candidates, text)

    result: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        absolute = _absolute_url(raw, page_url)
        if not _is_valid_image(absolute):
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        result.append(absolute)
        if len(result) >= max_images:
            break

    return "|".join(result)


def row_has_images(row: dict[str, object]) -> bool:
    for key, value in row.items():
        key_low = str(key or "").lower()
        if any(token in key_low for token in ("imagem", "imagens", "image", "images", "foto", "gallery")):
            if str(value or "").strip():
                return True
    return False
