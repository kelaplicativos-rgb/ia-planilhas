from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
TIMEOUT = 10
MAX_PAGES = 80
MAX_PRODUCTS = 1200
ESTOQUE_DISPONIVEL_PADRAO = 1000


@dataclass
class StockFlashConfig:
    estoque_disponivel: int = ESTOQUE_DISPONIVEL_PADRAO
    max_pages: int = MAX_PAGES
    max_products: int = MAX_PRODUCTS


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


def _discover_product_links(start_urls: list[str], config: StockFlashConfig) -> list[str]:
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


def _json_number(objects: list[dict[str, Any]], keys: list[str]) -> int | None:
    value = _json_first(objects, keys)
    if not value:
        return None
    found = re.search(r"\d+", value.replace(".", ""))
    if not found:
        return None
    try:
        return max(0, int(found.group(0)))
    except Exception:
        return None


def _extract_sku(text: str, url: str, objects: list[dict[str, Any]]) -> str:
    from_json = _json_first(objects, ["sku", "codigo", "código", "code", "reference", "referencia", "referência", "id", "productId"])
    if from_json:
        return from_json[:80]

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
        first_number = re.match(r"(\d+)", parts[-1])
        if first_number:
            return first_number.group(1)[:80]
        return re.sub(r"[^A-Za-z0-9._-]+", "-", parts[-1]).strip("-")[:80]
    return ""


def _extract_title(soup: BeautifulSoup, objects: list[dict[str, Any]], fallback: str) -> str:
    title = _json_first(objects, ["name", "title", "titulo", "título"])
    if title:
        return title[:220]
    h1 = soup.find("h1")
    if h1:
        value = _clean_text(h1.get_text(" ", strip=True))
        if value:
            return value[:220]
    meta = soup.find("meta", attrs={"property": "og:title"}) or soup.find("meta", attrs={"name": "title"})
    if meta and meta.get("content"):
        return _clean_text(meta.get("content"))[:220]
    return fallback[:220]


def _availability(text: str, html: str, objects: list[dict[str, Any]]) -> tuple[str, bool | None]:
    raw = _json_first(objects, ["availability", "disponibilidade", "available", "isAvailable"])
    low = raw.lower()
    if any(t in low for t in ["outofstock", "out of stock", "esgot", "indispon", "false", "nao", "não"]):
        return "Indisponível", False
    if any(t in low for t in ["instock", "in stock", "dispon", "true", "sim"]):
        return "Disponível", True

    page = (html + " " + text).lower()
    unavailable = ["esgotado", "sem estoque", "indisponível", "indisponivel", "fora de estoque", "avise-me", "aviseme"]
    available = ["comprar agora", ">comprar<", "adicionar ao carrinho", "colocar no carrinho", "comprar"]

    if any(term in page for term in unavailable):
        return "Indisponível", False
    if any(term in page for term in available):
        return "Disponível", True
    return "Não identificado", None


def _real_stock(text: str, html: str, objects: list[dict[str, Any]]) -> int | None:
    json_value = _json_number(
        objects,
        ["stock", "estoque", "quantity", "quantidade", "availableStock", "inventoryQuantity", "saldo", "maxQuantity"],
    )
    if json_value is not None:
        return json_value

    haystack = html + "\n" + text
    patterns = [
        r"estoque[^0-9]{0,30}(\d{1,5})",
        r"quantidade[^0-9]{0,30}(\d{1,5})",
        r"saldo[^0-9]{0,30}(\d{1,5})",
        r"availableStock[^0-9]{0,30}(\d{1,5})",
        r"inventoryQuantity[^0-9]{0,30}(\d{1,5})",
        r"data-stock=[\"'](\d{1,5})[\"']",
        r"data-estoque=[\"'](\d{1,5})[\"']",
        r"max=[\"'](\d{1,5})[\"']",
    ]
    for pattern in patterns:
        match = re.search(pattern, haystack, flags=re.IGNORECASE)
        if match:
            try:
                return max(0, int(match.group(1)))
            except Exception:
                pass
    return None


def _resolve_stock(text: str, html: str, objects: list[dict[str, Any]], estoque_disponivel: int) -> tuple[int, str, str]:
    real = _real_stock(text, html, objects)
    if real is not None:
        return int(real), "REAL DO SITE", "Disponível" if int(real) > 0 else "Indisponível"

    label, available = _availability(text, html, objects)
    if available is False:
        return 0, "INDISPONÍVEL AUTO", "Indisponível"
    if available is True:
        valor = max(0, int(estoque_disponivel or ESTOQUE_DISPONIVEL_PADRAO))
        return valor, f"DISPONÍVEL AUTO {valor}", "Disponível"
    return 0, "NÃO INFORMADO", "Não identificado"


def _extract_stock_product(url: str, session: requests.Session, config: StockFlashConfig) -> dict[str, object] | None:
    try:
        html = _fetch(url, session)
    except Exception:
        return None

    soup = _soup(html)
    objects = _json_objects(soup)
    text = _clean_text(soup.get_text(" ", strip=True))
    sku = _extract_sku(text + " " + html, url, objects)
    title = _extract_title(soup, objects, fallback=sku or url)
    estoque, origem_estoque, disponibilidade = _resolve_stock(text, html, objects, config.estoque_disponivel)

    if not sku and not title:
        return None

    return {
        "Código": sku,
        "SKU site": sku,
        "Descrição": title,
        "Estoque": int(estoque),
        "Quantidade": int(estoque),
        "Disponibilidade": disponibilidade,
        "Origem do estoque": origem_estoque,
        "URL do produto": url,
        "Origem": "site_estoque_flash",
    }


def crawl_stock_flash_dataframe(raw_urls: str, estoque_disponivel: int = ESTOQUE_DISPONIVEL_PADRAO) -> pd.DataFrame:
    start_urls = [_normalize_url(u) for u in re.split(r"[\n,;\s]+", str(raw_urls or "")) if str(u).strip()]
    if not start_urls:
        return pd.DataFrame()

    config = StockFlashConfig(estoque_disponivel=max(0, int(estoque_disponivel or ESTOQUE_DISPONIVEL_PADRAO)))
    urls = _discover_product_links(start_urls, config)
    ordered: list[str] = []
    seen: set[str] = set()
    for url in urls:
        normalized = _normalize_url(url)
        if normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)

    session = _new_session()
    rows: list[dict[str, object]] = []
    for url in ordered[: config.max_products]:
        item = _extract_stock_product(url, session, config)
        if item:
            rows.append(item)

    return pd.DataFrame(rows).fillna("")
