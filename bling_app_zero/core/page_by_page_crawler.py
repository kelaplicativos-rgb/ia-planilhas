from __future__ import annotations

import json
import re
from html import unescape
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

DEFAULT_TIMEOUT = 20
PRODUCT_PATH_RE = re.compile(r"/produto/", re.I)
PRICE_RE = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+[,.]\d{2})")
IMAGE_EXT_RE = re.compile(r"\.(jpg|jpeg|png|webp)(?:$|[?#])", re.I)
ANY_IMAGE_RE = re.compile(r"(?:https?:)?//[^\s\"'<>]+|[^\s\"'<>]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s\"'<>]*)?", re.I)
GTIN_RE = re.compile(r"\b(\d{8}|\d{12}|\d{13}|\d{14})\b")


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
    }


def fetch_html(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    response = requests.get(url, headers=_headers(), timeout=timeout)
    response.raise_for_status()
    return response.text or ""


def normalize_url(url: str, base_url: str) -> str:
    raw = unescape(str(url or "")).strip().replace("\\/", "/")
    if raw.startswith("//"):
        raw = "https:" + raw
    return urljoin(base_url, raw)


def is_product_url(url: str) -> bool:
    parsed = urlparse(str(url or ""))
    return bool(parsed.scheme and parsed.netloc and PRODUCT_PATH_RE.search(parsed.path))


def _same_host(url: str, hosts: set[str]) -> bool:
    return not hosts or urlparse(url).netloc.lower() in hosts


def discover_product_urls(seed_urls: Iterable[str], *, max_products: Optional[int] = None, use_sitemap: bool = False) -> list[str]:
    seeds = [str(u or "").strip() for u in seed_urls if str(u or "").strip()]
    hosts = {urlparse(u).netloc.lower() for u in seeds if urlparse(u).netloc}
    discovered: list[str] = []
    seen: set[str] = set()
    pages = list(seeds)
    seen_pages: set[str] = set()

    def add_product(candidate: str) -> bool:
        clean = normalize_url(candidate, candidate).split("#")[0].split("?")[0]
        if not is_product_url(clean) or not _same_host(clean, hosts) or clean in seen:
            return False
        seen.add(clean)
        discovered.append(clean)
        return bool(max_products and len(discovered) >= max_products)

    for seed in seeds:
        if add_product(seed):
            return discovered

    while pages:
        page = pages.pop(0)
        if page in seen_pages or len(seen_pages) > 80:
            continue
        seen_pages.add(page)
        try:
            html = fetch_html(page)
        except Exception:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select("a[href]"):
            href = normalize_url(a.get("href", ""), page)
            if add_product(href):
                return discovered
            if _same_host(href, hosts) and href not in seen_pages and len(pages) < 120:
                low = href.lower()
                if any(x in low for x in ("page=", "pagina=", "/page/")):
                    pages.append(href)
    return discovered


def _clean_text(value: object) -> str:
    text = unescape("" if value is None else str(value))
    text = text.replace("\ufeff", " ").replace("\u200b", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _normalize_price(value: object) -> str:
    matches = PRICE_RE.findall(_clean_text(value))
    values: list[float] = []
    for raw in matches:
        txt = raw.replace(".", "").replace(",", ".") if "," in raw else raw
        try:
            val = float(txt)
        except Exception:
            continue
        if val > 0:
            values.append(val)
    return f"{max(values):.2f}" if values else ""


def _json_ld_products(soup: BeautifulSoup) -> list[dict]:
    found: list[dict] = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text(" ", strip=True))
        except Exception:
            continue
        stack = payload if isinstance(payload, list) else [payload]
        while stack:
            item = stack.pop(0)
            if isinstance(item, dict):
                types = item.get("@type")
                type_list = types if isinstance(types, list) else [types]
                if "product" in {str(t).lower() for t in type_list if t}:
                    found.append(item)
                graph = item.get("@graph")
                if isinstance(graph, list):
                    stack.extend(graph)
            elif isinstance(item, list):
                stack.extend(item)
    return found


def _first_meta(soup: BeautifulSoup, *names: str) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return str(tag.get("content") or "").strip()
    return ""


def _add_image(candidates: list[str], value: object) -> None:
    raw = str(value or "").replace("\\/", "/")
    if not raw:
        return
    for part in raw.split(","):
        token = part.strip().split(" ")[0]
        if token:
            candidates.append(token)
    candidates.extend(ANY_IMAGE_RE.findall(raw))


def _valid_image(url: str) -> bool:
    low = url.lower()
    if not low.startswith(("http://", "https://")):
        return False
    if any(bad in low for bad in ("logo", "sprite", "placeholder", "favicon", "pixel", "analytics", "base64")):
        return False
    return bool(IMAGE_EXT_RE.search(low)) or any(x in low for x in ("image", "imagem", "foto", "product", "produto", "media", "cdn"))


def _extract_images(soup: BeautifulSoup, page_url: str, seed_values: Iterable[object] = ()) -> str:
    candidates: list[str] = []
    for value in seed_values:
        _add_image(candidates, value)
    attrs = ("content", "src", "data-src", "data-original", "data-zoom-image", "data-large_image", "data-large-image", "data-lazy", "data-lazy-src", "srcset", "data-srcset", "href", "style")
    for tag in soup.select("meta, img, source, a[href], [style]"):
        for attr in attrs:
            value = tag.get(attr)
            if value:
                _add_image(candidates, value)
    for script in soup.select("script"):
        txt = script.string or script.get_text(" ", strip=True)
        if txt and any(ext in txt.lower() for ext in (".jpg", ".jpeg", ".png", ".webp")):
            _add_image(candidates, txt)
    images: list[str] = []
    seen: set[str] = set()
    for raw in candidates:
        url = normalize_url(str(raw).strip().strip('"\'[]{}()'), page_url)
        if _valid_image(url) and url not in seen:
            seen.add(url)
            images.append(url)
        if len(images) >= 20:
            break
    return "|".join(images)


def _extract_from_json_ld(soup: BeautifulSoup) -> tuple[dict[str, str], list[object]]:
    data: dict[str, str] = {}
    images: list[object] = []
    for obj in _json_ld_products(soup):
        data["Descrição"] = data.get("Descrição") or _clean_text(obj.get("name"))
        brand = obj.get("brand", {}).get("name") if isinstance(obj.get("brand"), dict) else obj.get("brand")
        data["Marca"] = data.get("Marca") or _clean_text(brand)
        data["Código"] = data.get("Código") or _clean_text(obj.get("sku") or obj.get("mpn"))
        data["Cód no fornecedor"] = data.get("Cód no fornecedor") or _clean_text(obj.get("sku") or obj.get("mpn"))
        data["GTIN/EAN"] = data.get("GTIN/EAN") or _clean_text(obj.get("gtin13") or obj.get("gtin14") or obj.get("gtin12") or obj.get("gtin8"))
        data["Categoria"] = data.get("Categoria") or _clean_text(obj.get("category"))
        image = obj.get("image")
        if isinstance(image, list):
            images.extend(image)
        elif image:
            images.append(image)
        offers = obj.get("offers")
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        if isinstance(offers, dict):
            data["Preço"] = data.get("Preço") or _normalize_price(offers.get("price"))
    return data, images


def extract_product_from_page(page_url: str, html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    full_text = soup.get_text(" ", strip=True)
    data, json_images = _extract_from_json_ld(soup)

    title = data.get("Descrição") or _first_meta(soup, "og:title", "twitter:title")
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True)
    data["Descrição"] = _clean_text(title)

    desc = _first_meta(soup, "description", "og:description", "twitter:description")
    if desc:
        data["Descrição complementar"] = _clean_text(desc)
        data["Descrição curta"] = _clean_text(desc)

    price = data.get("Preço") or _normalize_price(_first_meta(soup, "product:price:amount", "og:price:amount", "price")) or _normalize_price(full_text)
    if price:
        data["Preço"] = price
        data["Preço unitário"] = price
        data["Preço unitário (OBRIGATÓRIO)"] = price

    gtin = data.get("GTIN/EAN") or ""
    if not gtin:
        match = GTIN_RE.search(full_text)
        gtin = match.group(1) if match else ""
    if gtin:
        data["GTIN/EAN"] = gtin

    images = _extract_images(soup, page_url, json_images)
    if images:
        data["URL Imagens Externas"] = images
        data["Imagens"] = images

    data["Link Externo"] = page_url
    data["URL do Produto"] = page_url
    data["Fonte captura"] = "pagina_produto"
    return {k: _clean_text(v) for k, v in data.items() if _clean_text(v)}


def crawl_product_pages(seed_urls: Iterable[str], *, max_products: Optional[int] = None, use_sitemap: bool = False) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for product_url in discover_product_urls(seed_urls, max_products=max_products, use_sitemap=use_sitemap):
        try:
            rows.append(extract_product_from_page(product_url, fetch_html(product_url)))
        except Exception as exc:
            rows.append({"Link Externo": product_url, "URL do Produto": product_url, "Fonte captura": "pagina_produto_erro", "Erro captura": str(exc)})
    return rows


def crawl_product_pages_dataframe(seed_urls: Iterable[str], *, max_products: Optional[int] = None, use_sitemap: bool = False) -> pd.DataFrame:
    return pd.DataFrame(crawl_product_pages(seed_urls, max_products=max_products, use_sitemap=use_sitemap))
