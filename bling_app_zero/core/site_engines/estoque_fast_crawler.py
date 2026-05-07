from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from typing import Callable, Iterable, Optional

import pandas as pd
from bs4 import BeautifulSoup

from bling_app_zero.core.page_by_page_crawler import fetch_html
from bling_app_zero.core.product_url_discovery_infinity import discover_product_urls_infinity

ProgressCallback = Optional[Callable[[int, int, str], None]]

GTIN_RE = re.compile(r"\b(\d{8}|\d{12}|\d{13}|\d{14})\b")
SKU_RE = re.compile(r"(?:sku|cod(?:igo)?|ref(?:erencia)?|modelo)\s*[:#\-]?\s*([a-z0-9._\-/]+)", re.I)
DEFAULT_MAX_WORKERS = 12
DEFAULT_MAX_PRODUCTS = 5000
MAX_WORKERS_HARD_LIMIT = 32

OUT_OF_STOCK_TERMS = (
    "sem estoque",
    "indisponivel",
    "indisponível",
    "esgotado",
    "fora de estoque",
    "produto indisponivel",
    "produto indisponível",
)
IN_STOCK_TERMS = (
    "em estoque",
    "disponivel",
    "disponível",
    "comprar",
    "adicionar ao carrinho",
    "produto disponivel",
    "produto disponível",
)
REAL_STOCK_PATTERNS = (
    re.compile(r"(?:estoque|saldo|quantidade|qtd)\s*(?:dispon[ií]vel)?\s*[:#\-]?\s*(\d+(?:[\.,]\d+)?)", re.I),
    re.compile(r"(\d+(?:[\.,]\d+)?)\s*(?:unidades|unidade|itens|item|pe[cç]as|pe[cç]a)\s*(?:em estoque|dispon[ií]veis|dispon[ií]vel)", re.I),
    re.compile(r"(?:restam|apenas|somente)\s*(\d+(?:[\.,]\d+)?)\s*(?:unidades|unidade|itens|item|pe[cç]as|pe[cç]a)?", re.I),
    re.compile(r"(?:stock|inventory|available_quantity|quantity_available|stock_quantity|qty)\s*[=:]\s*[\"']?(\d+(?:[\.,]\d+)?)", re.I),
)
STOCK_ATTR_NAMES = (
    "data-stock",
    "data-estoque",
    "data-quantity",
    "data-qty",
    "data-saldo",
    "data-available-quantity",
    "data-stock-quantity",
    "stock",
    "quantity",
    "qty",
)


def _clean_text(value: object) -> str:
    text = unescape("" if value is None else str(value))
    text = text.replace("\ufeff", " ").replace("\u200b", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _requested_set(requested_fields: Iterable[str] | None) -> set[str]:
    return {str(item or "").strip().lower() for item in (requested_fields or []) if str(item or "").strip()}


def _normalize_qty(value: object) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    match = re.search(r"\d+(?:[\.,]\d+)?", text)
    if not match:
        return ""
    number = match.group(0).replace(",", ".")
    try:
        numeric = float(number)
    except Exception:
        return ""
    if numeric < 0:
        return ""
    if numeric.is_integer():
        return str(int(numeric))
    return str(numeric).rstrip("0").rstrip(".")


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
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name}) or soup.find(attrs={"itemprop": name})
        if tag and tag.get("content"):
            return str(tag.get("content") or "").strip()
        if tag and tag.get("value"):
            return str(tag.get("value") or "").strip()
    return ""


def _extract_quantity_from_obj(obj: object) -> str:
    if isinstance(obj, list):
        for item in obj:
            found = _extract_quantity_from_obj(item)
            if found:
                return found
        return ""
    if not isinstance(obj, dict):
        return ""

    for key in (
        "inventoryLevel",
        "stockLevel",
        "stockQuantity",
        "quantity",
        "qty",
        "availableQuantity",
        "available_quantity",
        "quantityAvailable",
        "availabilityCount",
    ):
        value = obj.get(key)
        if isinstance(value, dict):
            nested = _extract_quantity_from_obj(value)
            if nested:
                return nested
        qty = _normalize_qty(value)
        if qty:
            return qty

    offers = obj.get("offers")
    found = _extract_quantity_from_obj(offers)
    if found:
        return found

    additional = obj.get("additionalProperty") or obj.get("additionalProperties")
    if isinstance(additional, list):
        for item in additional:
            if not isinstance(item, dict):
                continue
            name = _clean_text(item.get("name") or item.get("propertyID") or item.get("@type")).lower()
            if any(term in name for term in ("estoque", "saldo", "quantidade", "stock", "inventory", "quantity")):
                qty = _normalize_qty(item.get("value"))
                if qty:
                    return qty
    return ""


def _extract_quantity_from_attrs(soup: BeautifulSoup) -> str:
    for tag in soup.find_all(True):
        attrs = getattr(tag, "attrs", {}) or {}
        for name in STOCK_ATTR_NAMES:
            if name in attrs:
                qty = _normalize_qty(attrs.get(name))
                if qty:
                    return qty
    return ""


def _extract_quantity_from_scripts(soup: BeautifulSoup) -> str:
    for script in soup.find_all("script"):
        text = script.string or script.get_text(" ", strip=True) or ""
        if not text:
            continue
        for pattern in REAL_STOCK_PATTERNS:
            match = pattern.search(text)
            if match:
                qty = _normalize_qty(match.group(1))
                if qty:
                    return qty
    return ""


def _extract_quantity_from_text(text: str) -> str:
    for pattern in REAL_STOCK_PATTERNS:
        match = pattern.search(text)
        if match:
            qty = _normalize_qty(match.group(1))
            if qty:
                return qty
    return ""


def _stock_from_sources(soup: BeautifulSoup, product: dict, full_text: str) -> tuple[str, str]:
    lower = full_text.lower()
    if any(term in lower for term in OUT_OF_STOCK_TERMS):
        return "0", "texto_indisponivel"

    for source_name, extractor in (
        ("json_ld", lambda: _extract_quantity_from_obj(product)),
        ("meta_itemprop", lambda: _normalize_qty(_first_meta(soup, "inventoryLevel", "stockLevel", "stock", "quantity"))),
        ("html_attrs", lambda: _extract_quantity_from_attrs(soup)),
        ("scripts", lambda: _extract_quantity_from_scripts(soup)),
        ("texto", lambda: _extract_quantity_from_text(full_text)),
    ):
        qty = extractor()
        if qty:
            return qty, source_name

    if any(term in lower for term in IN_STOCK_TERMS):
        return "1", "fallback_disponivel_sem_quantidade"
    return "", "nao_encontrado"


def _extract_one(product_url: str, requested_fields: Iterable[str] | None = None) -> dict[str, str]:
    fields = _requested_set(requested_fields)
    html = fetch_html(product_url)
    soup = BeautifulSoup(html, "html.parser")
    products = _json_ld_products(soup)
    product = products[0] if products else {}
    needs_text = bool(fields.intersection({"nome", "descricao", "sku", "gtin", "estoque"}))
    full_text = soup.get_text(" ", strip=True) if needs_text else ""
    row: dict[str, str] = {}

    if fields.intersection({"nome", "descricao"}):
        name = _clean_text(product.get("name")) if isinstance(product, dict) else ""
        if not name:
            name = _first_meta(soup, "og:title", "twitter:title")
        if not name and soup.title:
            name = soup.title.get_text(" ", strip=True)
        if name:
            row["Produto"] = _clean_text(name)
            row["Nome"] = _clean_text(name)
            row["Descrição"] = _clean_text(name)

    if "sku" in fields:
        sku = _clean_text(product.get("sku") or product.get("mpn")) if isinstance(product, dict) else ""
        if not sku:
            match = SKU_RE.search(full_text)
            sku = match.group(1) if match else ""
        if sku:
            row["Código"] = _clean_text(sku)
            row["SKU"] = _clean_text(sku)
            row["Cód no fornecedor"] = _clean_text(sku)

    if "gtin" in fields:
        gtin = _clean_text(product.get("gtin13") or product.get("gtin14") or product.get("gtin12") or product.get("gtin8")) if isinstance(product, dict) else ""
        if not gtin:
            match = GTIN_RE.search(full_text)
            gtin = match.group(1) if match else ""
        if gtin:
            row["GTIN"] = gtin
            row["EAN"] = gtin
            row["GTIN/EAN"] = gtin

    if "estoque" in fields:
        stock, stock_source = _stock_from_sources(soup, product if isinstance(product, dict) else {}, full_text)
        if stock:
            row["Estoque"] = stock
            row["Quantidade"] = stock
            row["Saldo"] = stock
            row["Fonte estoque"] = stock_source

    if "url" in fields:
        row["Link Externo"] = product_url
        row["URL do Produto"] = product_url

    row.setdefault("Link Externo", product_url)
    row.setdefault("URL do Produto", product_url)
    row["Fonte captura"] = "estoque_fast_crawler"
    return {key: _clean_text(value) for key, value in row.items() if _clean_text(value)}


def crawl_estoque_fast_dataframe(
    seed_urls: Iterable[str],
    *,
    requested_fields: Iterable[str] | None,
    max_products: int = DEFAULT_MAX_PRODUCTS,
    max_workers: int = DEFAULT_MAX_WORKERS,
    progress_callback: ProgressCallback = None,
) -> pd.DataFrame:
    seed_list = [str(url or "").strip() for url in seed_urls if str(url or "").strip()]
    fields = _requested_set(requested_fields)
    if not seed_list or not fields:
        return pd.DataFrame()

    product_urls = discover_product_urls_infinity(seed_list, max_products=int(max_products or DEFAULT_MAX_PRODUCTS))
    total = len(product_urls)
    if total == 0:
        return pd.DataFrame()

    rows_by_url: dict[str, dict[str, str]] = {}
    workers = max(1, min(int(max_workers or DEFAULT_MAX_WORKERS), MAX_WORKERS_HARD_LIMIT, total))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_extract_one, url, fields): url for url in product_urls}
        for done, future in enumerate(as_completed(futures), start=1):
            url = futures[future]
            try:
                rows_by_url[url] = future.result()
            except Exception as exc:
                rows_by_url[url] = {"Link Externo": url, "URL do Produto": url, "Fonte captura": "estoque_fast_crawler_erro", "Erro captura": str(exc)}
            if progress_callback:
                progress_callback(done, total, url)

    return pd.DataFrame([rows_by_url[url] for url in product_urls if url in rows_by_url])
