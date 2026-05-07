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
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlsplit, urlunsplit

from bs4 import BeautifulSoup

IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".avif")
BAD = (
    "logo", "sprite", "placeholder", "favicon", "pixel", "analytics", "base64", "whatsapp", "instagram",
    "facebook", "facebook.com/tr", "doubleclick", "googletagmanager", "google-analytics", "googleadservices",
    "googleads", "adsystem", "hotjar", "clarity", "tracking", "track", "noscript", "blank", "loading",
    "spacer", "transparent", "svg+xml", "banner", "payment", "pagamento", "boleto", "pix", "visa",
    "mastercard", "ssl", "security", "seguro", "captcha", "avatar", "footer", "header", "menu", "icone", "icon",
)
GOOD_HINTS = (
    "image", "imagem", "foto", "media", "cdn", "upload", "uploads", "storage", "files", "catalog", "catalogo",
    "produto", "product", "products", "produtos", "fotos", "shop",
)
DROP_QUERY_PARAMS = {
    "fbclid", "gclid", "gbraid", "wbraid", "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "mc_cid", "mc_eid", "igshid", "ref", "source", "campaign",
}
ATTRS = (
    "content", "src", "data-src", "data-original", "data-zoom-image", "data-large_image", "data-large-image",
    "data-lazy", "data-lazy-src", "srcset", "data-srcset", "href", "style",
)
SELECTORS = (
    "meta[property='og:image']", "meta[property='og:image:secure_url']", "meta[name='twitter:image']",
    "meta[itemprop='image']", "[itemprop='image']", "img", "source", "a[href]", "[style]",
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


def _strip_tracking_query(url: str) -> str:
    parsed = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in DROP_QUERY_PARAMS]
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query, doseq=True), ""))


def _is_product_page(url: str) -> bool:
    path = urlparse(url).path.lower()
    return any(x in path for x in ("/produto/", "/product/", "/produtos/", "/products/")) and not any(ext in path for ext in IMG_EXT)


def _valid(url: str) -> bool:
    low = str(url or "").lower().strip()
    if not low.startswith(("http://", "https://")):
        return False
    if _is_product_page(low):
        return False
    if any(x in low for x in BAD):
        return False
    if re.search(r"(?:^|[-_/])(?:1x1|2x2|pixel|spacer|transparent)(?:[-_.?/]|$)", low):
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


def extract_safe_product_images(page_url: str, html: str, extra_candidates: Iterable[object] | None = None, max_images: int = 12) -> str:
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
        url = _strip_tracking_query(_abs(page_url, item))
        if not _valid(url):
            continue
        parsed = urlsplit(url.lower())
        key = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        if key in seen:
            continue
        seen.add(key)
        result.append(url)
        if len(result) >= max_images:
            break
    return "|".join(result)
