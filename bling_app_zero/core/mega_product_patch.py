from __future__ import annotations

"""Patch de extração para produtos de fornecedores estilo Mega Center.

Regras aplicadas:
- `Código` e `Cód no fornecedor` vêm do ID da URL: /produto/390748-...
- `GTIN/EAN` pode continuar sendo o SKU/EAN informado pelo site.
- Imagens são buscadas no HTML inteiro da página do produto, incluindo galeria,
  data attributes, srcset, JSON-LD e scripts.
- Imagens grandes/originais/zoom são priorizadas antes de miniaturas.
- A saída final de `URL Imagens Externas` sempre fica separada por `|`.
"""

import json
import re
from html import unescape
from typing import Iterable
from urllib.parse import urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from bling_app_zero.core.product_image_extractor import normalize_image_urls


PRODUCT_CODE_RE = re.compile(r"/produto/(\d+)(?:[-_/]|$)", re.IGNORECASE)
IMAGE_URL_RE = re.compile(r"https?:\\?/\\?/[^\s'\"<>]+?\.(?:jpg|jpeg|png|webp|avif)(?:[^\s'\"<>]*)?", re.IGNORECASE)
REL_IMAGE_RE = re.compile(r"(?:/|\.\./)[^\s'\"<>]+?\.(?:jpg|jpeg|png|webp|avif)(?:[^\s'\"<>]*)?", re.IGNORECASE)
IMAGE_EXT_CUT_RE = re.compile(r"^(.*?\.(?:jpg|jpeg|png|webp|avif))(?:$|[?#].*)", re.IGNORECASE)

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
    "tracking",
    "whatsapp",
    "instagram",
    "svg+xml",
    "banner",
    "icon",
)

GOOD_GALLERY_HINTS = (
    "produto",
    "product",
    "upload",
    "uploads",
    "catalog",
    "catalogo",
    "image",
    "imagem",
    "foto",
    "fotos",
    "galeria",
    "gallery",
    "zoom",
    "large",
    "original",
)


def supplier_code_from_product_url(url: object) -> str:
    match = PRODUCT_CODE_RE.search(str(url or ""))
    return match.group(1) if match else ""


def _cut_after_image_extension(url: str) -> str:
    text = str(url or "").strip()
    match = IMAGE_EXT_CUT_RE.match(text)
    if match:
        return match.group(1)
    return text


def _clean_url(raw: object, base_url: str) -> str:
    text = unescape(str(raw or "").strip().strip('"\''))
    if not text:
        return ""
    text = text.replace("\\/", "/")
    text = text.split(" ", 1)[0].strip()

    for separator in ("|", "@png", "@jpg", "@jpeg", "@webp", "@avif"):
        if separator in text.lower():
            text = re.split(re.escape(separator), text, flags=re.IGNORECASE)[0]
            break

    text = _cut_after_image_extension(text)
    if text.startswith("//"):
        text = "https:" + text

    absolute = urljoin(base_url, text)
    absolute = _cut_after_image_extension(absolute)
    try:
        parts = urlsplit(absolute)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))
    except Exception:
        return absolute


def _is_valid_product_image(url: str) -> bool:
    low = str(url or "").lower()
    if not low.startswith(("http://", "https://")):
        return False
    if any(fragment in low for fragment in BAD_IMAGE_FRAGMENTS):
        return False
    if re.search(r"\.(jpg|jpeg|png|webp|avif)(?:$|[?#])", low):
        return True
    return any(token in low for token in GOOD_GALLERY_HINTS)


def _image_score(url: str) -> int:
    low = str(url or "").lower()
    score = 0

    for token, points in (
        ("zoom", 120),
        ("original", 115),
        ("large", 105),
        ("full", 90),
        ("big", 80),
        ("grande", 80),
        ("galeria", 65),
        ("gallery", 65),
        ("produto", 55),
        ("product", 55),
        ("upload", 35),
        ("catalog", 30),
        ("cdn", 20),
    ):
        if token in low:
            score += points

    for width, height in re.findall(r"(\d{2,5})[xX](\d{2,5})", low):
        try:
            area = int(width) * int(height)
        except Exception:
            continue
        if area >= 1_000_000:
            score += 160
        elif area >= 500_000:
            score += 120
        elif area >= 160_000:
            score += 70
        elif area < 40_000:
            score -= 120

    for token, points in (
        ("thumbnail", -150),
        ("thumb", -140),
        ("small", -110),
        ("mini", -100),
        ("tiny", -100),
        ("80x80", -150),
        ("100x100", -140),
        ("150x150", -120),
        ("200x200", -90),
    ):
        if token in low:
            score += points

    if re.search(r"\.(webp|jpg|jpeg|png|avif)(?:$|[?#])", low):
        score += 20
    return score


def _add_candidate(candidates: list[str], seen: set[str], raw: object, base_url: str) -> None:
    url = _clean_url(raw, base_url)
    if not url or not _is_valid_product_image(url):
        return
    key = url.lower()
    if key in seen:
        return
    seen.add(key)
    candidates.append(url)


def _walk_json_images(payload: object) -> Iterable[str]:
    stack = [payload]
    while stack:
        item = stack.pop(0)
        if isinstance(item, dict):
            for key, value in item.items():
                key_low = str(key).lower()
                if key_low in {"image", "images", "thumbnail", "url", "src", "large_image", "zoom_image"}:
                    if isinstance(value, str):
                        yield value
                    elif isinstance(value, list):
                        for sub in value:
                            if isinstance(sub, str):
                                yield sub
                            else:
                                stack.append(sub)
                    elif isinstance(value, dict):
                        stack.append(value)
                elif isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(item, list):
            stack.extend(item)


def extract_all_product_images(html: str, page_url: str, *, max_items: int = 20) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    candidates: list[str] = []
    seen: set[str] = set()

    selectors = (
        "meta[property='og:image']",
        "meta[property='og:image:secure_url']",
        "meta[name='twitter:image']",
        "[itemprop='image']",
        "img",
        "source",
        "a[href]",
    )
    attrs = (
        "content",
        "src",
        "href",
        "srcset",
        "data-src",
        "data-original",
        "data-zoom-image",
        "data-large_image",
        "data-large-image",
        "data-full",
        "data-full-src",
        "data-image",
        "data-img",
        "data-lazy",
        "data-lazy-src",
        "data-srcset",
    )
    for selector in selectors:
        for tag in soup.select(selector):
            for attr in attrs:
                value = tag.get(attr)
                if not value:
                    continue
                if "srcset" in attr:
                    for part in str(value).split(","):
                        _add_candidate(candidates, seen, part.strip().split(" ")[0], page_url)
                else:
                    _add_candidate(candidates, seen, value, page_url)

            for attr_name, attr_value in tag.attrs.items():
                if not str(attr_name).lower().startswith("data-"):
                    continue
                if isinstance(attr_value, list):
                    attr_value = " ".join(str(v) for v in attr_value)
                raw_attr = unescape(str(attr_value)).replace("\\/", "/")
                raw_attr = re.sub(r"@(png|jpg|jpeg|webp|avif)", " ", raw_attr, flags=re.IGNORECASE)
                for match in IMAGE_URL_RE.findall(raw_attr):
                    _add_candidate(candidates, seen, match, page_url)
                for match in REL_IMAGE_RE.findall(raw_attr):
                    _add_candidate(candidates, seen, match, page_url)

    for script in soup.select("script"):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        raw_unescaped = unescape(raw).replace("\\/", "/")
        raw_unescaped = re.sub(r"@(png|jpg|jpeg|webp|avif)", " ", raw_unescaped, flags=re.IGNORECASE)
        for match in IMAGE_URL_RE.findall(raw_unescaped):
            _add_candidate(candidates, seen, match, page_url)
        for match in REL_IMAGE_RE.findall(raw_unescaped):
            _add_candidate(candidates, seen, match, page_url)
        if "application/ld+json" in str(script.get("type", "")).lower():
            try:
                payload = json.loads(raw)
            except Exception:
                continue
            for image in _walk_json_images(payload):
                _add_candidate(candidates, seen, image, page_url)

    candidates.sort(key=_image_score, reverse=True)
    return normalize_image_urls("|".join(candidates[:max_items]), page_url=page_url, max_images=max_items)


def install_mega_product_patch() -> None:
    """Instala patch no crawler antes do fluxo Streamlit carregar."""
    try:
        from bling_app_zero.core import page_by_page_crawler as crawler
    except Exception:
        return

    original_extract = getattr(crawler, "extract_product_from_page", None)
    if not callable(original_extract):
        return
    if getattr(original_extract, "_mega_product_patch", False):
        return

    def patched_extract_product_from_page(page_url: str, html: str) -> dict[str, str]:
        data = original_extract(page_url, html)
        if not isinstance(data, dict):
            data = {}

        product_url = data.get("Link Externo") or page_url
        supplier_code = supplier_code_from_product_url(product_url)
        if supplier_code:
            data["Código"] = supplier_code
            data["Cód no fornecedor"] = supplier_code

        images = extract_all_product_images(html or "", product_url)
        if images:
            data["URL Imagens Externas"] = images
        elif data.get("URL Imagens Externas"):
            data["URL Imagens Externas"] = normalize_image_urls(data.get("URL Imagens Externas"), page_url=product_url)

        return data

    patched_extract_product_from_page._mega_product_patch = True  # type: ignore[attr-defined]
    crawler.extract_product_from_page = patched_extract_product_from_page
