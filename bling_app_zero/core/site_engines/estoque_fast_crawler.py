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
from bling_app_zero.core.site_engines.stock_feed_engine import find_stock_in_domain_feeds
from bling_app_zero.core.site_engines.stock_value_engine import extract_real_stock_value

ProgressCallback = Optional[Callable[[int, int, str], None]]

GTIN_RE = re.compile(r"\b(\d{8}|\d{12}|\d{13}|\d{14})\b")
SKU_RE = re.compile(r"(?:sku|cod(?:igo)?|ref(?:erencia)?|modelo)\s*[:#\-]?\s*([a-z0-9._\-/]+)", re.I)
DEFAULT_MAX_WORKERS = 12
DEFAULT_MAX_PRODUCTS = 5000
MAX_WORKERS_HARD_LIMIT = 32


def _clean_text(value: object) -> str:
    text = unescape("" if value is None else str(value))
    text = text.replace("\ufeff", " ").replace("\u200b", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _requested_set(requested_fields: Iterable[str] | None) -> set[str]:
    return {str(item or "").strip().lower() for item in (requested_fields or []) if str(item or "").strip()}


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


def _apply_stock(row: dict[str, str], quantity: str, source: str, confidence: str) -> None:
    if not quantity:
        return
    row["Estoque"] = quantity
    row["Quantidade"] = quantity
    row["Saldo"] = quantity
    row["Fonte estoque"] = source
    row["Confianca estoque"] = confidence


def _extract_one(product_url: str, requested_fields: Iterable[str] | None = None) -> dict[str, str]:
    fields = _requested_set(requested_fields)
    html = fetch_html(product_url)
    soup = BeautifulSoup(html, "html.parser")
    products = _json_ld_products(soup)
    product = products[0] if products else {}
    needs_text = bool(fields.intersection({"nome", "descricao", "sku", "gtin"}))
    full_text = soup.get_text(" ", strip=True) if needs_text else ""
    row: dict[str, str] = {}
    product_name = ""
    sku = ""
    gtin = ""

    if fields.intersection({"nome", "descricao"}):
        product_name = _clean_text(product.get("name")) if isinstance(product, dict) else ""
        if not product_name:
            product_name = _first_meta(soup, "og:title", "twitter:title")
        if not product_name and soup.title:
            product_name = soup.title.get_text(" ", strip=True)
        if product_name:
            row["Produto"] = _clean_text(product_name)
            row["Nome"] = _clean_text(product_name)
            row["Descrição"] = _clean_text(product_name)

    if "sku" in fields:
        sku = _clean_text(product.get("sku") or product.get("mpn")) if isinstance(product, dict) else ""
        if not sku:
            if not full_text:
                full_text = soup.get_text(" ", strip=True)
            match = SKU_RE.search(full_text)
            sku = match.group(1) if match else ""
        if sku:
            row["Código"] = _clean_text(sku)
            row["SKU"] = _clean_text(sku)
            row["Cód no fornecedor"] = _clean_text(sku)

    if "gtin" in fields:
        gtin = _clean_text(product.get("gtin13") or product.get("gtin14") or product.get("gtin12") or product.get("gtin8")) if isinstance(product, dict) else ""
        if not gtin:
            if not full_text:
                full_text = soup.get_text(" ", strip=True)
            match = GTIN_RE.search(full_text)
            gtin = match.group(1) if match else ""
        if gtin:
            row["GTIN"] = gtin
            row["EAN"] = gtin
            row["GTIN/EAN"] = gtin

    if "estoque" in fields:
        stock_result = extract_real_stock_value(html, page_url=product_url)
        if stock_result.quantity and stock_result.confidence == "alta":
            _apply_stock(row, stock_result.quantity, stock_result.source, stock_result.confidence)
        else:
            feed_result = find_stock_in_domain_feeds(
                product_url,
                sku=sku,
                gtin=gtin,
                name=product_name,
            )
            if feed_result.quantity:
                _apply_stock(row, feed_result.quantity, feed_result.source, feed_result.confidence)
                row["Fonte estoque feed"] = feed_result.feed_url
            elif stock_result.quantity:
                _apply_stock(row, stock_result.quantity, stock_result.source, stock_result.confidence)

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
