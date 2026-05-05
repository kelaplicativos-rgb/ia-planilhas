from __future__ import annotations

import json
import re
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
TIMEOUT = 7
MAX_PAGES = 80
MAX_PRODUCTS = 1200
MAX_WORKERS = 14


KNOWN_BRANDS = [
    "JBL", "Samsung", "Apple", "Xiaomi", "Motorola", "LG", "Sony", "Philips", "Multilaser",
    "Lenovo", "Dell", "HP", "Asus", "Acer", "Intelbras", "Positivo", "Mondial", "Britânia",
    "Britania", "Elgin", "Aiwa", "Havit", "Baseus", "Amazfit", "Haylou", "Lenoxx", "Knup",
    "Exbom", "Inova", "Kaidi", "Tomate", "MXT", "Importado", "B-Max", "Bmax", "Gshield",
]


@dataclass
class ProductFlashConfig:
    max_pages: int = MAX_PAGES
    max_products: int = MAX_PRODUCTS
    max_workers: int = MAX_WORKERS


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def _normalize_url(url: str) -> str:
    raw = str(url or "").strip()
    parsed = urlparse(raw)
    if not parsed.scheme:
        parsed = urlparse("https://" + raw)
    parsed = parsed._replace(fragment="")
    return urlunparse(parsed)


def _same_domain(url: str, domain: str) -> bool:
    return urlparse(url).netloc.replace("www.", "") == domain.replace("www.", "")


def _new_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        }
    )
    return session


def _fetch(url: str, session: requests.Session) -> str:
    response = session.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return response.text or ""


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or "", "html.parser")


def _absolute(base: str, href: str) -> str:
    return _normalize_url(urljoin(base, href or ""))


def _is_product_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return "/produto/" in path or "/product/" in path or "/p/" in path


def _should_follow(url: str) -> bool:
    low = url.lower()
    blocked = [
        "/carrinho",
        "/checkout",
        "/login",
        "/conta",
        "/minha-conta",
        "whatsapp",
        "mailto:",
        "tel:",
        "javascript:",
        "#",
    ]
    return not any(item in low for item in blocked)


def _discover_product_links(start_urls: list[str], config: ProductFlashConfig) -> list[str]:
    if not start_urls:
        return []

    session = _new_session()
    domain = urlparse(start_urls[0]).netloc.replace("www.", "")
    queue: deque[str] = deque(start_urls)
    visited: set[str] = set()
    products: list[str] = []
    seen_products: set[str] = set()

    while queue and len(visited) < config.max_pages and len(products) < config.max_products:
        url = _normalize_url(queue.popleft())
        if url in visited or not _same_domain(url, domain) or not _should_follow(url):
            continue
        visited.add(url)

        if _is_product_url(url):
            if url not in seen_products:
                seen_products.add(url)
                products.append(url)
            continue

        try:
            html = _fetch(url, session)
        except Exception:
            continue

        soup = _soup(html)
        for a in soup.find_all("a", href=True):
            href = _absolute(url, str(a.get("href") or ""))
            if not _same_domain(href, domain) or not _should_follow(href):
                continue
            if _is_product_url(href):
                if href not in seen_products:
                    seen_products.add(href)
                    products.append(href)
                    if len(products) >= config.max_products:
                        break
            elif len(visited) + len(queue) < config.max_pages:
                queue.append(href)
    return products


def _safe_json(raw: str) -> Any | None:
    try:
        return json.loads(raw)
    except Exception:
        return None


def _walk_json(value: Any) -> Iterable[Any]:
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_json(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_json(item)


def _json_objects(soup: BeautifulSoup) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        payload = _safe_json(script.string or script.get_text(" ", strip=True) or "")
        if payload is not None:
            for item in _walk_json(payload):
                if isinstance(item, dict):
                    objects.append(item)

    next_data = soup.find("script", id="__NEXT_DATA__")
    if next_data:
        payload = _safe_json(next_data.string or next_data.get_text(" ", strip=True) or "")
        if payload is not None:
            for item in _walk_json(payload):
                if isinstance(item, dict):
                    objects.append(item)
    return objects


def _json_first(objects: list[dict[str, Any]], keys: list[str]) -> str:
    wanted = {k.lower() for k in keys}
    for obj in objects:
        for key, value in obj.items():
            if str(key).lower() not in wanted or value in (None, "", [], {}):
                continue
            if isinstance(value, dict):
                for sub in ["name", "nome", "title", "titulo"]:
                    if value.get(sub):
                        return _clean_text(value.get(sub))
                continue
            if isinstance(value, list):
                continue
            return _clean_text(value)
    return ""


def _extract_code(text: str, url: str, objects: list[dict[str, Any]]) -> str:
    value = _json_first(objects, ["sku", "codigo", "código", "code", "reference", "referencia", "referência", "id", "productId"])
    if value:
        return value[:80]

    patterns = [
        r"C[ÓO]D\s*[:\-]?\s*([0-9A-Za-z._\-]+)",
        r"SKU\s*[:\-]?\s*([0-9A-Za-z._\-]+)",
        r"REF\s*[:\-]?\s*([0-9A-Za-z._\-]+)",
        r"Refer[êe]ncia\s*[:\-]?\s*([0-9A-Za-z._\-]+)",
        r"data-product-id=[\"'](\d+)[\"']",
        r"data-produto-id=[\"'](\d+)[\"']",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_text(match.group(1))[:80]

    parts = [p for p in urlparse(url).path.split("/") if p]
    if parts:
        first = re.match(r"(\d+)", parts[-1])
        if first:
            return first.group(1)[:80]
        return re.sub(r"[^A-Za-z0-9._-]+", "-", parts[-1]).strip("-")[:80]
    return ""


def _extract_title(soup: BeautifulSoup, objects: list[dict[str, Any]], fallback: str) -> str:
    title = _json_first(objects, ["name", "title", "titulo", "título"])
    if title:
        return title[:240]
    h1 = soup.find("h1")
    if h1:
        value = _clean_text(h1.get_text(" ", strip=True))
        if value:
            return value[:240]
    meta = soup.find("meta", attrs={"property": "og:title"}) or soup.find("meta", attrs={"name": "title"})
    if meta and meta.get("content"):
        return _clean_text(meta.get("content"))[:240]
    return fallback[:240]


def _extract_gtin(text: str, objects: list[dict[str, Any]]) -> str:
    value = _json_first(objects, ["gtin", "gtin8", "gtin12", "gtin13", "gtin14", "ean", "barcode", "codigoBarras"])
    if value:
        digits = re.sub(r"\D+", "", value)
        if len(digits) in {8, 12, 13, 14}:
            return digits
    for candidate in re.findall(r"\b\d{8,14}\b", text):
        if len(candidate) in {8, 12, 13, 14}:
            return candidate
    return ""


def _money(value: object) -> str:
    raw = _clean_text(value)
    if not raw:
        return ""
    if re.search(r"\d+\.\d{1,2}$", raw):
        try:
            return f"{float(raw):.2f}".replace(".", ",")
        except Exception:
            pass
    found = re.search(r"([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+,[0-9]{2}|[0-9]+\.[0-9]{1,2})", raw)
    if not found:
        return ""
    value = found.group(1)
    if "." in value and "," not in value:
        try:
            return f"{float(value):.2f}".replace(".", ",")
        except Exception:
            return value
    return value


def _extract_price(text: str, objects: list[dict[str, Any]]) -> str:
    value = _money(_json_first(objects, ["price", "salePrice", "sale_price", "preco", "preço", "valor", "valorVenda"])
    )
    if value:
        return value
    prices = re.findall(r"R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+,[0-9]{2}|[0-9]+\.[0-9]{1,2})", text)
    values = [_money(p) for p in prices if _money(p)]
    return values[-1] if values else ""


def _extract_images_fast(soup: BeautifulSoup, base_url: str, objects: list[dict[str, Any]]) -> str:
    images: list[str] = []
    meta = soup.find("meta", attrs={"property": "og:image"}) or soup.find("meta", attrs={"name": "twitter:image"})
    if meta and meta.get("content"):
        images.append(_absolute(base_url, str(meta.get("content"))))

    for obj in objects:
        for key, value in obj.items():
            if str(key).lower() not in {"image", "images", "imagem", "imagens"}:
                continue
            if isinstance(value, str):
                images.append(_absolute(base_url, value))
            elif isinstance(value, list):
                for item in value[:6]:
                    if isinstance(item, str):
                        images.append(_absolute(base_url, item))
                    elif isinstance(item, dict):
                        candidate = item.get("url") or item.get("src") or item.get("image")
                        if candidate:
                            images.append(_absolute(base_url, str(candidate)))

    cleaned: list[str] = []
    seen: set[str] = set()
    for url in images:
        low = url.lower()
        if any(skip in low for skip in ["logo", "sprite", "placeholder", "loading", "icon", "favicon", "whatsapp", "facebook.com/tr"]):
            continue
        if url not in seen:
            seen.add(url)
            cleaned.append(url)
    return "|".join(cleaned[:8])


def _extract_brand(title: str, objects: list[dict[str, Any]]) -> str:
    value = _json_first(objects, ["brand", "marca", "manufacturer", "fabricante"])
    if value:
        return value[:80]
    haystack = f" {title} "
    for known in KNOWN_BRANDS:
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(known)}(?![A-Za-z0-9])", haystack, flags=re.IGNORECASE):
            return known.upper() if known.lower() == "jbl" else known
    return ""


def _extract_category(soup: BeautifulSoup, objects: list[dict[str, Any]]) -> str:
    value = _json_first(objects, ["category", "categoria", "categoryName", "nomeCategoria"])
    if value:
        return value[:180]
    bits: list[str] = []
    for selector in [".breadcrumb a", "[class*=breadcrumb] a", "nav a"]:
        for tag in soup.select(selector)[:8]:
            text = _clean_text(tag.get_text(" ", strip=True))
            if text and text.lower() not in {"home", "inicio", "início", "produtos"} and text not in bits:
                bits.append(text)
    return " > ".join(bits[:5])


def _extract_short_description(soup: BeautifulSoup, objects: list[dict[str, Any]]) -> str:
    value = _json_first(objects, ["description", "descricao", "descrição", "shortDescription"])
    if value:
        return value[:900]
    meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if meta and meta.get("content"):
        return _clean_text(meta.get("content"))[:900]
    return ""


def _extract_product(url: str, config: ProductFlashConfig) -> dict[str, object] | None:
    session = _new_session()
    try:
        html = _fetch(url, session)
    except Exception:
        return None

    soup = _soup(html)
    objects = _json_objects(soup)
    text = _clean_text(soup.get_text(" ", strip=True))
    code = _extract_code(text + " " + html, url, objects)
    title = _extract_title(soup, objects, fallback=code or url)

    if not code and not title:
        return None

    return {
        "Código": code,
        "Descrição": title,
        "Descrição complementar": _extract_short_description(soup, objects),
        "Unidade": "UN",
        "NCM": "",
        "GTIN/EAN": _extract_gtin(text, objects),
        "Preço unitário": _extract_price(text, objects),
        "Preço de custo": "",
        "Marca": _extract_brand(title, objects),
        "Categoria": _extract_category(soup, objects),
        "URL imagens externas": _extract_images_fast(soup, url, objects),
        "URL do produto": url,
        "Origem": "site_cadastro_flash_sem_estoque",
    }


def crawl_product_flash_dataframe(raw_urls: str) -> pd.DataFrame:
    start_urls = [_normalize_url(u) for u in re.split(r"[\n,;\s]+", str(raw_urls or "")) if str(u).strip()]
    if not start_urls:
        return pd.DataFrame()

    config = ProductFlashConfig()
    urls = _discover_product_links(start_urls, config)
    ordered: list[str] = []
    seen: set[str] = set()
    for url in urls:
        normalized = _normalize_url(url)
        if normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)

    rows: list[dict[str, object]] = []
    workers = max(1, min(int(config.max_workers or MAX_WORKERS), 28, len(ordered) or 1))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_map = {executor.submit(_extract_product, url, config): url for url in ordered[: config.max_products]}
        for future in as_completed(future_map):
            try:
                item = future.result()
            except Exception:
                item = None
            if item:
                rows.append(item)

    return pd.DataFrame(rows).fillna("")
