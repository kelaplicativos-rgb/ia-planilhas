from __future__ import annotations

"""Extração única e robusta de imagens de páginas de produto.

Este módulo transforma HTML + dados estruturados em `URL Imagens Externas`
no padrão do Bling, usando `|` como separador.
"""

import json
import re
from html import unescape
from typing import Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

IMAGE_URL_RE = re.compile(
    r"(?:https?:)?//[^\s\"'<>\\]+?\.(?:jpg|jpeg|png|webp|avif)(?:\?[^\s\"'<>\\]*)?|[^\s\"'<>\\]+\.(?:jpg|jpeg|png|webp|avif)(?:\?[^\s\"'<>\\]*)?",
    re.IGNORECASE,
)
IMAGE_FIELD_URL_RE = re.compile(
    r"(?:image|images|src|url|thumbnail|thumbnailUrl|contentUrl)\s*[\"']?\s*[:=]\s*[\[\{\s]*[\"']?(https?:/{1,2}[^\s\"'<>]+?\.(?:jpg|jpeg|png|webp|avif)(?:\?[^\s\"'<>]*)?)",
    re.IGNORECASE,
)
IMAGE_EXT_RE = re.compile(r"\.(jpg|jpeg|png|webp|avif)(?:$|[?#])", re.IGNORECASE)
IMAGE_EXT_CUT_RE = re.compile(r"^(.*?\.(?:jpg|jpeg|png|webp|avif))(?:$|[?#].*)", re.IGNORECASE)
FIELD_MARKER_RE = re.compile(r"(?:image|images|src|url)[\"']?\s*[:=]", re.IGNORECASE)
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
    "/produto/image",
    "/product/image",
    "megacentereletronicos.com.br/produto/image",
)
GOOD_IMAGE_HINTS = (
    "image_studio",
    "product_images",
    "produto_imagens",
    "imagem_produto",
    "foto_produto",
    "upload",
    "uploads",
    "cdn",
    "media",
    "catalog",
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
    raw = unescape(str(value or "")).strip().replace("\\/", "/")
    raw = raw.replace("&quot;", '"').replace("&#34;", '"').replace("&#39;", "'")
    return raw


def _fix_scheme_slashes(url: str) -> str:
    return re.sub(r"^(https?):/+(?!/)", r"\1://", str(url or "").strip(), flags=re.IGNORECASE)


def _cut_after_image_extension(url: str) -> str:
    text = str(url or "").strip()
    match = IMAGE_EXT_CUT_RE.match(text)
    return match.group(1) if match else text


def _embedded_field_url(raw: str) -> str:
    text = _clean_raw(raw)
    matches = IMAGE_FIELD_URL_RE.findall(text)
    if matches:
        return _fix_scheme_slashes(matches[-1])
    marker_match = re.search(
        r"(?:image|images|src|url)[\"']?\s*[:=]\s*[\[\{\s]*[\"']?(https?:/{1,2}.+)$",
        text,
        re.IGNORECASE,
    )
    if marker_match:
        return _fix_scheme_slashes(marker_match.group(1))
    return text


def _absolute_url(value: object, page_url: str) -> str:
    raw = _embedded_field_url(_clean_raw(value).strip().strip('"\'[]{}()'))
    if not raw:
        return ""

    for separator in ("|", "@png", "@jpg", "@jpeg", "@webp", "@avif"):
        if separator in raw.lower():
            raw = re.split(re.escape(separator), raw, flags=re.IGNORECASE)[0]
            break

    raw = _fix_scheme_slashes(_cut_after_image_extension(raw))
    if raw.startswith("//"):
        raw = "https:" + raw
    absolute = urljoin(page_url, raw)
    absolute = _fix_scheme_slashes(_cut_after_image_extension(absolute))

    try:
        parts = urlsplit(absolute)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
    except Exception:
        return absolute


def _add_candidate(candidates: list[str], value: object) -> None:
    raw = _clean_raw(value)
    if not raw:
        return

    for embedded in IMAGE_FIELD_URL_RE.findall(raw):
        candidates.append(_fix_scheme_slashes(embedded))

    raw = raw.replace("|", " ")
    raw = re.sub(r"@(png|jpg|jpeg|webp|avif)", " ", raw, flags=re.IGNORECASE)

    for part in re.split(r"\s+|,", raw):
        token = part.strip().split(" ")[0]
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
    if lower.count("http://") + lower.count("https://") > 1:
        return False
    if FIELD_MARKER_RE.search(lower):
        return False
    if not IMAGE_EXT_RE.search(lower):
        return False
    return True


def normalize_image_urls(value: object, page_url: str = "", max_images: int = 20) -> str:
    """Normaliza qualquer valor de imagens para o padrão Bling separado por `|`.

    Só mantém URLs reais de arquivo de imagem. Links de página de produto, mesmo
    quando vêm colados com `image":"...`, são descartados.
    """
    candidates: list[str] = []
    raw = _clean_raw(value)
    if raw:
        for embedded in IMAGE_FIELD_URL_RE.findall(raw):
            candidates.append(_fix_scheme_slashes(embedded))
        for part in re.split(r"\s*\|\s*|\s+", raw):
            _add_candidate(candidates, part)
        _add_candidate(candidates, raw)

    result: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        url = _absolute_url(item, page_url)
        if not _is_valid_image(url):
            continue
        key = url.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(url)
        if len(result) >= max_images:
            break
    return "|".join(result)


def extract_product_images_from_html(page_url: str, html: str, extra_candidates: Iterable[object] | None = None, max_images: int = 20) -> str:
    """Retorna URLs reais de imagens separadas por `|`."""
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
        key = absolute.lower()
        if key in seen:
            continue
        seen.add(key)
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
