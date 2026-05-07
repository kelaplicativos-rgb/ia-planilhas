from __future__ import annotations

"""Motor complementar para buscar estoque em feeds/XML do próprio domínio.

Uso pretendido:
- Só deve ser acionado depois que a página do produto não retorna quantidade
  real com alta confiança.
- Busca arquivos comuns de feed/sitemap no mesmo domínio.
- Tenta casar produto por URL, SKU, GTIN ou nome.
- Prioriza quantidade real; quando só houver availability, retorna 1/0.
"""

import json
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from html import unescape
from typing import Iterable
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from bling_app_zero.core.site_engines.stock_value_engine import normalize_quantity

DEFAULT_TIMEOUT = 12
MAX_FEED_BYTES = 5_000_000

FEED_CANDIDATES = (
    "/products.xml",
    "/produtos.xml",
    "/product.xml",
    "/feed.xml",
    "/feeds.xml",
    "/google-shopping.xml",
    "/googleshopping.xml",
    "/merchant.xml",
    "/catalog.xml",
    "/catalogo.xml",
    "/sitemap_products.xml",
    "/sitemap_produtos.xml",
    "/sitemap.xml",
)

QUANTITY_KEYS = (
    "quantity",
    "qty",
    "stock",
    "estoque",
    "saldo",
    "inventory",
    "inventorylevel",
    "stocklevel",
    "stockquantity",
    "availablequantity",
    "quantityavailable",
    "available_quantity",
    "stock_quantity",
)
AVAILABILITY_KEYS = (
    "availability",
    "disponibilidade",
    "available",
    "status",
    "g:availability",
)
ID_KEYS = (
    "id",
    "g:id",
    "sku",
    "mpn",
    "codigo",
    "código",
    "gtin",
    "ean",
    "g:gtin",
    "link",
    "url",
    "g:link",
    "title",
    "titulo",
    "g:title",
)


@dataclass(frozen=True)
class StockFeedResult:
    quantity: str
    source: str
    confidence: str
    feed_url: str = ""
    reason: str = ""

    @property
    def found(self) -> bool:
        return bool(str(self.quantity or "").strip())


def _clean_text(value: object) -> str:
    text = unescape("" if value is None else str(value))
    text = text.replace("\ufeff", " ").replace("\u200b", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 AppleWebKit/537.36 Chrome/124 Safari/537.36",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
    }


def _base_url(page_url: str) -> str:
    parsed = urlparse(str(page_url or ""))
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def candidate_feed_urls(page_url: str) -> list[str]:
    base = _base_url(page_url)
    if not base:
        return []
    urls: list[str] = []
    seen: set[str] = set()
    for path in FEED_CANDIDATES:
        url = urljoin(base, path)
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def _fetch_feed(url: str) -> str:
    try:
        response = requests.get(url, headers=_headers(), timeout=DEFAULT_TIMEOUT)
        if response.status_code >= 400:
            return ""
        content_type = str(response.headers.get("content-type") or "").lower()
        text = response.text or ""
        if len(response.content or b"") > MAX_FEED_BYTES:
            return ""
        if not text.strip():
            return ""
        if not any(token in content_type for token in ("xml", "json", "text", "rss", "atom", "html")):
            if not text.lstrip().startswith(("<", "{", "[")):
                return ""
        return text
    except Exception:
        return ""


def _norm_key(value: object) -> str:
    text = _clean_text(value).lower()
    text = re.sub(r"[^a-z0-9:_-]+", "", text)
    return text


def _flatten_xml_element(element: ET.Element) -> dict[str, str]:
    row: dict[str, str] = {}
    for child in element.iter():
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        key = _norm_key(tag)
        value = _clean_text(child.text)
        if key and value and key not in row:
            row[key] = value
        for attr_key, attr_val in (child.attrib or {}).items():
            attr_name = _norm_key(attr_key)
            attr_value = _clean_text(attr_val)
            if attr_name and attr_value and attr_name not in row:
                row[attr_name] = attr_value
    return row


def _rows_from_xml(text: str) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(text.encode("utf-8"))
    except Exception:
        return []

    rows: list[dict[str, str]] = []
    for element in root.iter():
        tag = element.tag.split("}")[-1].lower() if isinstance(element.tag, str) else ""
        if tag in {"item", "entry", "product", "produto", "url"}:
            row = _flatten_xml_element(element)
            if row:
                rows.append(row)
    if rows:
        return rows

    row = _flatten_xml_element(root)
    return [row] if row else []


def _flatten_json(obj: object, prefix: str = "") -> dict[str, str]:
    row: dict[str, str] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            next_key = _norm_key(key)
            full_key = f"{prefix}{next_key}" if not prefix else f"{prefix}.{next_key}"
            if isinstance(value, (dict, list)):
                row.update(_flatten_json(value, full_key))
            else:
                clean = _clean_text(value)
                if clean:
                    row[full_key] = clean
                    row.setdefault(next_key, clean)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            row.update(_flatten_json(item, f"{prefix}.{idx}" if prefix else str(idx)))
    return row


def _rows_from_json(text: str) -> list[dict[str, str]]:
    try:
        payload = json.loads(text)
    except Exception:
        return []

    if isinstance(payload, list):
        return [_flatten_json(item) for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("products", "produtos", "items", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [_flatten_json(item) for item in value if isinstance(item, dict)]
        return [_flatten_json(payload)]
    return []


def _rows_from_html(text: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(text or "", "html.parser")
    rows: list[dict[str, str]] = []
    for script in soup.find_all("script"):
        raw = script.string or script.get_text(" ", strip=True) or ""
        if raw.lstrip().startswith(("{", "[")):
            rows.extend(_rows_from_json(raw))
    return rows


def _rows_from_feed(text: str) -> list[dict[str, str]]:
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        return _rows_from_json(text)
    if stripped.startswith("<"):
        rows = _rows_from_xml(text)
        if rows:
            return rows
        return _rows_from_html(text)
    return []


def _token_values(row: dict[str, str]) -> list[str]:
    values: list[str] = []
    for key, value in row.items():
        nk = _norm_key(key)
        if nk in {_norm_key(k) for k in ID_KEYS} or any(term in nk for term in ("id", "sku", "gtin", "ean", "link", "url", "title", "titulo", "codigo")):
            values.append(_clean_text(value).lower())
    return values


def _match_row(row: dict[str, str], *, page_url: str, sku: str = "", gtin: str = "", name: str = "") -> bool:
    haystack = " | ".join(_token_values(row)).lower()
    if not haystack:
        return False
    page_url_l = _clean_text(page_url).lower().rstrip("/")
    if page_url_l and page_url_l in haystack:
        return True
    if sku and _clean_text(sku).lower() in haystack:
        return True
    if gtin and _clean_text(gtin).lower() in haystack:
        return True
    clean_name = _clean_text(name).lower()
    return bool(clean_name and clean_name in haystack)


def _quantity_from_row(row: dict[str, str]) -> tuple[str, str]:
    for key, value in row.items():
        nk = _norm_key(key)
        if any(stock_key in nk for stock_key in QUANTITY_KEYS):
            qty = normalize_quantity(value)
            if qty:
                return qty, key

    for key, value in row.items():
        nk = _norm_key(key)
        if nk in {_norm_key(k) for k in AVAILABILITY_KEYS} or "availability" in nk or "dispon" in nk:
            text = _clean_text(value).lower()
            if any(term in text for term in ("out_of_stock", "outofstock", "sem estoque", "indispon", "esgotado")):
                return "0", key
            if any(term in text for term in ("in_stock", "instock", "em estoque", "dispon", "available")):
                return "1", key
    return "", ""


def find_stock_in_domain_feeds(
    page_url: str,
    *,
    sku: str = "",
    gtin: str = "",
    name: str = "",
    feed_urls: Iterable[str] | None = None,
) -> StockFeedResult:
    candidates = list(feed_urls or candidate_feed_urls(page_url))
    for feed_url in candidates:
        text = _fetch_feed(feed_url)
        if not text:
            continue
        rows = _rows_from_feed(text)
        for row in rows:
            if not _match_row(row, page_url=page_url, sku=sku, gtin=gtin, name=name):
                continue
            qty, source_key = _quantity_from_row(row)
            if qty:
                confidence = "media" if qty == "1" else "alta"
                return StockFeedResult(qty, "feed_xml", confidence, feed_url, f"campo={source_key}")
    return StockFeedResult("", "feed_nao_encontrado", "nenhuma", "", "nenhum feed com estoque encontrado")


__all__ = ["StockFeedResult", "candidate_feed_urls", "find_stock_in_domain_feeds"]
