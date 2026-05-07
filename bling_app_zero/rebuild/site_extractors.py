from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from .sanitizer import clean_gtin, clean_text, normalize_price, normalize_stock


@dataclass(frozen=True)
class ProductSnapshot:
    url: str
    name: str = ""
    sku: str = ""
    gtin: str = ""
    price: str = ""
    stock: str = ""
    brand: str = ""
    supplier: str = "Não definido"
    category: str = ""
    images: str = ""
    ncm: str = ""


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
}


def fetch_html(url: str, timeout: int = 20) -> str:
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response.text


def _iter_json_ld(soup: BeautifulSoup) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except Exception:
            continue
        stack = parsed if isinstance(parsed, list) else [parsed]
        while stack:
            item = stack.pop(0)
            if isinstance(item, dict):
                if "@graph" in item and isinstance(item["@graph"], list):
                    stack.extend(item["@graph"])
                items.append(item)
            elif isinstance(item, list):
                stack.extend(item)
    return items


def _first(*values: Any) -> str:
    for value in values:
        if isinstance(value, list):
            value = value[0] if value else ""
        if isinstance(value, dict):
            value = value.get("name") or value.get("url") or ""
        text = clean_text(value)
        if text:
            return text
    return ""


def _meta(soup: BeautifulSoup, *keys: str) -> str:
    for key in keys:
        tag = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key}) or soup.find("meta", attrs={"itemprop": key})
        if tag and tag.get("content"):
            return clean_text(tag.get("content"))
    return ""


def _extract_product_json(soup: BeautifulSoup) -> dict[str, Any]:
    for item in _iter_json_ld(soup):
        item_type = item.get("@type")
        types = item_type if isinstance(item_type, list) else [item_type]
        if any(str(t).lower() == "product" for t in types):
            return item
    return {}


def _extract_price(product: dict[str, Any], soup: BeautifulSoup) -> str:
    offers = product.get("offers") if isinstance(product, dict) else {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    price = ""
    if isinstance(offers, dict):
        price = _first(offers.get("price"), offers.get("lowPrice"), offers.get("highPrice"), offers.get("priceSpecification"))
    price = price or _meta(soup, "product:price:amount", "price", "og:price:amount")
    if not price:
        text = soup.get_text(" ", strip=True)
        match = re.search(r"R\$\s*\d{1,3}(?:\.\d{3})*(?:,\d{2})|R\$\s*\d+(?:,\d{2})", text)
        price = match.group(0) if match else ""
    return normalize_price(price)


def _extract_stock(product: dict[str, Any], soup: BeautifulSoup) -> str:
    offers = product.get("offers") if isinstance(product, dict) else {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    availability = ""
    if isinstance(offers, dict):
        availability = _first(offers.get("availability"))
    text = f"{availability} {soup.get_text(' ', strip=True)}".lower()
    if any(token in text for token in ("sem estoque", "indisponível", "indisponivel", "esgotado", "outofstock")):
        return "0"
    stock = normalize_stock(text)
    if stock:
        return stock
    if any(token in text for token in ("instock", "em estoque", "comprar", "adicionar ao carrinho")):
        return "1"
    return ""


def _extract_images(product: dict[str, Any], soup: BeautifulSoup, base_url: str) -> str:
    raw_images: list[str] = []
    image_value = product.get("image") if isinstance(product, dict) else ""
    if isinstance(image_value, list):
        raw_images.extend(str(x) for x in image_value)
    elif image_value:
        raw_images.append(str(image_value))
    for key in ("og:image", "twitter:image"):
        meta = _meta(soup, key)
        if meta:
            raw_images.append(meta)
    for img in soup.find_all("img"):
        candidate = img.get("src") or img.get("data-src") or img.get("data-original") or ""
        alt = clean_text(img.get("alt"))
        src = clean_text(candidate)
        if not src:
            continue
        low = src.lower()
        if any(bad in low for bad in ("logo", "sprite", "placeholder", "loading", "icon", "whatsapp")):
            continue
        if alt or any(ext in low for ext in (".jpg", ".jpeg", ".png", ".webp")):
            raw_images.append(src)
    final: list[str] = []
    seen: set[str] = set()
    for img in raw_images:
        absolute = urljoin(base_url, clean_text(img))
        if absolute and absolute not in seen:
            seen.add(absolute)
            final.append(absolute)
        if len(final) >= 12:
            break
    return "|".join(final)


def _extract_category(product: dict[str, Any], soup: BeautifulSoup) -> str:
    category = _first(product.get("category") if isinstance(product, dict) else "")
    if category:
        return category
    crumbs = []
    for selector in (".breadcrumb a", "nav[aria-label*=breadcrumb] a", "[class*=breadcrumb] a"):
        for tag in soup.select(selector):
            text = clean_text(tag.get_text(" ", strip=True))
            if text and text.lower() not in {"home", "início", "inicio"}:
                crumbs.append(text)
        if crumbs:
            break
    return " > ".join(dict.fromkeys(crumbs))


def extract_product_snapshot(url: str) -> ProductSnapshot:
    html = fetch_html(url)
    soup = BeautifulSoup(html, "lxml")
    product = _extract_product_json(soup)

    brand_value = product.get("brand") if isinstance(product, dict) else ""
    name = _first(
        product.get("name") if isinstance(product, dict) else "",
        _meta(soup, "og:title", "twitter:title"),
        soup.title.string if soup.title else "",
        soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else "",
    )
    sku = _first(product.get("sku") if isinstance(product, dict) else "", product.get("mpn") if isinstance(product, dict) else "")
    text = soup.get_text(" ", strip=True)
    if not sku:
        sku_match = re.search(r"(?:SKU|C[ÓO]D(?:IGO)?|REF(?:ER[ÊE]NCIA)?)[\s:.-]*([A-Z0-9._/-]{2,40})", text, flags=re.I)
        sku = sku_match.group(1) if sku_match else ""
    gtin = clean_gtin(_first(
        product.get("gtin") if isinstance(product, dict) else "",
        product.get("gtin8") if isinstance(product, dict) else "",
        product.get("gtin12") if isinstance(product, dict) else "",
        product.get("gtin13") if isinstance(product, dict) else "",
        product.get("gtin14") if isinstance(product, dict) else "",
    ))
    if not gtin:
        gtin_match = re.search(r"(?:GTIN|EAN|C[ÓO]DIGO DE BARRAS)[\s:.-]*(\d{8,14})", text, flags=re.I)
        gtin = clean_gtin(gtin_match.group(1) if gtin_match else "")

    return ProductSnapshot(
        url=url,
        name=name,
        sku=clean_text(sku),
        gtin=gtin,
        price=_extract_price(product, soup),
        stock=_extract_stock(product, soup),
        brand=_first(brand_value),
        supplier="Não definido",
        category=_extract_category(product, soup),
        images=_extract_images(product, soup, url),
        ncm="",
    )
