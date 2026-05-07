from __future__ import annotations

import json
import re
from html import unescape
from typing import Iterable, Optional
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from bling_app_zero.core.product_image_extractor_safe import extract_safe_product_images
from bling_app_zero.core.product_url_discovery_infinity import discover_product_urls_infinity

DEFAULT_TIMEOUT = 20
PRODUCT_PATH_RE = re.compile(r"/produto/", re.I)
PRICE_RE = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+[,.]\d{2})")
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


def discover_product_urls(seed_urls: Iterable[str], *, max_products: Optional[int] = None, use_sitemap: bool = False) -> list[str]:
    return discover_product_urls_infinity(seed_urls, max_products=max_products)


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


def _requested_set(requested_fields: Iterable[str] | None) -> set[str]:
    return {str(item or "").strip().lower() for item in (requested_fields or []) if str(item or "").strip()}


def _wants(fields: set[str], *names: str) -> bool:
    return not fields or any(name in fields for name in names)


def _extract_from_json_ld(soup: BeautifulSoup, requested_fields: Iterable[str] | None = None) -> tuple[dict[str, str], list[object]]:
    fields = _requested_set(requested_fields)
    data: dict[str, str] = {}
    images: list[object] = []
    for obj in _json_ld_products(soup):
        if _wants(fields, "nome", "descricao"):
            data["Descrição"] = data.get("Descrição") or _clean_text(obj.get("name"))
        if _wants(fields, "marca"):
            brand = obj.get("brand", {}).get("name") if isinstance(obj.get("brand"), dict) else obj.get("brand")
            data["Marca"] = data.get("Marca") or _clean_text(brand)
        if _wants(fields, "sku"):
            data["Código"] = data.get("Código") or _clean_text(obj.get("sku") or obj.get("mpn"))
            data["Cód no fornecedor"] = data.get("Cód no fornecedor") or _clean_text(obj.get("sku") or obj.get("mpn"))
        if _wants(fields, "gtin"):
            data["GTIN/EAN"] = data.get("GTIN/EAN") or _clean_text(obj.get("gtin13") or obj.get("gtin14") or obj.get("gtin12") or obj.get("gtin8"))
        if _wants(fields, "categoria"):
            data["Categoria"] = data.get("Categoria") or _clean_text(obj.get("category"))
        if _wants(fields, "imagens"):
            image = obj.get("image")
            if isinstance(image, list):
                images.extend(image)
            elif image:
                images.append(image)
        if _wants(fields, "preco"):
            offers = obj.get("offers")
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            if isinstance(offers, dict):
                data["Preço"] = data.get("Preço") or _normalize_price(offers.get("price"))
    return data, images


def extract_product_from_page(page_url: str, html: str, requested_fields: Iterable[str] | None = None) -> dict[str, str]:
    fields = _requested_set(requested_fields)
    soup = BeautifulSoup(html, "html.parser")
    data, json_images = _extract_from_json_ld(soup, fields)

    need_full_text = _wants(fields, "preco", "gtin", "estoque")
    full_text = soup.get_text(" ", strip=True) if need_full_text else ""

    if _wants(fields, "nome", "descricao"):
        title = data.get("Descrição") or _first_meta(soup, "og:title", "twitter:title")
        if not title and soup.title:
            title = soup.title.get_text(" ", strip=True)
        if title:
            data["Descrição"] = _clean_text(title)

    if _wants(fields, "descricao_complementar"):
        desc = _first_meta(soup, "description", "og:description", "twitter:description")
        if desc:
            data["Descrição complementar"] = _clean_text(desc)
            data["Descrição curta"] = _clean_text(desc)

    if _wants(fields, "preco"):
        price = data.get("Preço") or _normalize_price(_first_meta(soup, "product:price:amount", "og:price:amount", "price")) or _normalize_price(full_text)
        if price:
            data["Preço"] = price
            data["Preço unitário"] = price
            data["Preço unitário (OBRIGATÓRIO)"] = price

    if _wants(fields, "gtin"):
        gtin = data.get("GTIN/EAN") or ""
        if not gtin:
            match = GTIN_RE.search(full_text)
            gtin = match.group(1) if match else ""
        if gtin:
            data["GTIN/EAN"] = gtin

    if _wants(fields, "estoque"):
        lower_text = full_text.lower()
        if any(term in lower_text for term in ("sem estoque", "indisponivel", "indisponível", "esgotado", "fora de estoque")):
            data["Estoque"] = "0"
        elif any(term in lower_text for term in ("em estoque", "disponivel", "disponível", "comprar", "adicionar ao carrinho")):
            data["Estoque"] = "1"

    if _wants(fields, "imagens"):
        images = extract_safe_product_images(page_url, html, extra_candidates=json_images)
        if images:
            data["URL Imagens Externas"] = images
            data["Imagens"] = images

    if _wants(fields, "url"):
        data["Link Externo"] = page_url
        data["URL do Produto"] = page_url

    data.setdefault("Link Externo", page_url)
    data.setdefault("URL do Produto", page_url)
    data["Fonte captura"] = "pagina_produto"
    return {k: _clean_text(v) for k, v in data.items() if _clean_text(v)}


def crawl_product_pages(
    seed_urls: Iterable[str],
    *,
    max_products: Optional[int] = None,
    use_sitemap: bool = False,
    requested_fields: Iterable[str] | None = None,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for product_url in discover_product_urls(seed_urls, max_products=max_products, use_sitemap=use_sitemap):
        try:
            rows.append(extract_product_from_page(product_url, fetch_html(product_url), requested_fields=requested_fields))
        except Exception as exc:
            rows.append({"Link Externo": product_url, "URL do Produto": product_url, "Fonte captura": "pagina_produto_erro", "Erro captura": str(exc)})
    return rows


def crawl_product_pages_dataframe(
    seed_urls: Iterable[str],
    *,
    max_products: Optional[int] = None,
    use_sitemap: bool = False,
    requested_fields: Iterable[str] | None = None,
) -> pd.DataFrame:
    return pd.DataFrame(crawl_product_pages(seed_urls, max_products=max_products, use_sitemap=use_sitemap, requested_fields=requested_fields))
