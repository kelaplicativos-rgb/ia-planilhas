from __future__ import annotations

import json
import re
from collections import deque
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"
TIMEOUT = 18
MAX_PAGES = 80
MAX_PRODUCTS = 500


@dataclass
class CrawlConfig:
    estoque_padrao: int = 1
    max_pages: int = MAX_PAGES
    max_products: int = MAX_PRODUCTS


def _clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\xa0", " ")).strip()


def _normalize_url(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    if not parsed.scheme:
        parsed = urlparse("https://" + str(url or "").strip())
    parsed = parsed._replace(fragment="")
    return urlunparse(parsed)


def _same_domain(url: str, domain: str) -> bool:
    return urlparse(url).netloc.replace("www.", "") == domain.replace("www.", "")


def _fetch(url: str) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.text


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or "", "html.parser")


def _absolute(base: str, href: str) -> str:
    return _normalize_url(urljoin(base, href or ""))


def _is_product_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return "/produto/" in path or "/product/" in path


def _should_follow(url: str) -> bool:
    path = urlparse(url).path.lower()
    blocked = ["/carrinho", "/checkout", "/login", "/conta", "whatsapp", "mailto:", "tel:"]
    return not any(item in url.lower() or item in path for item in blocked)


def _discover_links(start_urls: list[str], config: CrawlConfig) -> list[str]:
    if not start_urls:
        return []

    domain = urlparse(start_urls[0]).netloc.replace("www.", "")
    queue: deque[str] = deque(start_urls)
    visited: set[str] = set()
    product_urls: list[str] = []
    product_seen: set[str] = set()

    while queue and len(visited) < config.max_pages and len(product_urls) < config.max_products:
        url = _normalize_url(queue.popleft())
        if url in visited or not _same_domain(url, domain) or not _should_follow(url):
            continue
        visited.add(url)

        try:
            html = _fetch(url)
        except Exception:
            continue

        soup = _soup(html)
        for a in soup.find_all("a", href=True):
            href = _absolute(url, str(a.get("href") or ""))
            if not _same_domain(href, domain) or not _should_follow(href):
                continue
            if _is_product_url(href):
                if href not in product_seen:
                    product_seen.add(href)
                    product_urls.append(href)
                    if len(product_urls) >= config.max_products:
                        break
            elif len(visited) + len(queue) < config.max_pages:
                queue.append(href)

    return product_urls


def _extract_json_ld(soup: BeautifulSoup) -> list[dict]:
    items: list[dict] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        if isinstance(payload, dict):
            graph = payload.get("@graph")
            if isinstance(graph, list):
                items.extend([x for x in graph if isinstance(x, dict)])
            else:
                items.append(payload)
        elif isinstance(payload, list):
            items.extend([x for x in payload if isinstance(x, dict)])
    return items


def _first_meta(soup: BeautifulSoup, names: Iterable[str]) -> str:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return _clean_text(tag.get("content"))
    return ""


def _extract_images(soup: BeautifulSoup, base_url: str) -> str:
    images: list[str] = []
    seen: set[str] = set()

    for item in [_first_meta(soup, ["og:image", "twitter:image"])] :
        if item:
            images.append(_absolute(base_url, item))

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-original")
        if not src:
            continue
        url = _absolute(base_url, str(src))
        low = url.lower()
        if any(skip in low for skip in ["logo", "sprite", "placeholder", "loading", "whatsapp"]):
            continue
        images.append(url)

    cleaned: list[str] = []
    for url in images:
        if url not in seen:
            seen.add(url)
            cleaned.append(url)
    return "|".join(cleaned[:12])


def _extract_code(text: str, url: str) -> str:
    patterns = [
        r"C[ÓO]D\s*[:\-]?\s*([0-9A-Za-z._\-]+)",
        r"SKU\s*[:\-]?\s*([0-9A-Za-z._\-]+)",
        r"REF\s*[:\-]?\s*([0-9A-Za-z._\-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _clean_text(match.group(1))[:60]
    parts = [p for p in urlparse(url).path.split("/") if p]
    if parts:
        return re.sub(r"[^A-Za-z0-9_-]+", "-", parts[-1]).strip("-")[:60]
    return ""


def _extract_gtin(text: str) -> str:
    candidates = re.findall(r"\b\d{8,14}\b", text)
    for candidate in candidates:
        if len(candidate) in {8, 12, 13, 14}:
            return candidate
    return ""


def _extract_prices(text: str) -> tuple[str, str]:
    prices = re.findall(r"R\$\s*([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+,[0-9]{2})", text)
    if not prices:
        return "", ""
    normal = [p.strip() for p in prices]
    preco_custo = normal[0]
    preco_venda = normal[-1] if len(normal) > 1 else normal[0]
    return preco_venda, preco_custo


def _extract_stock(text: str, html: str, config: CrawlConfig) -> int:
    low = text.lower()
    if any(term in low for term in ["esgotado", "sem estoque", "indisponível", "indisponivel", "fora de estoque"]):
        return 0

    explicit_patterns = [
        r"estoque[^0-9]{0,30}(\d{1,5})",
        r"quantidade[^0-9]{0,30}(\d{1,5})",
        r"availableStock[^0-9]{0,30}(\d{1,5})",
        r"stock[^0-9]{0,30}(\d{1,5})",
        r"max=[\"'](\d{1,5})[\"']",
    ]
    haystack = html + "\n" + text
    for pattern in explicit_patterns:
        match = re.search(pattern, haystack, flags=re.IGNORECASE)
        if match:
            try:
                return max(0, int(match.group(1)))
            except Exception:
                pass

    if any(term in low for term in ["em estoque", "adicionar", "comprar"]):
        return max(1, int(config.estoque_padrao or 1))
    return int(config.estoque_padrao or 0)


def _extract_category(soup: BeautifulSoup) -> str:
    bits: list[str] = []
    selectors = ["nav a", ".breadcrumb a", "[class*=breadcrumb] a", "[class*=categoria] a"]
    for selector in selectors:
        for tag in soup.select(selector):
            txt = _clean_text(tag.get_text(" ", strip=True))
            if txt and txt.lower() not in {"home", "início", "inicio", "produtos"} and txt not in bits:
                bits.append(txt)
    return " > ".join(bits[:5])


def _extract_description(soup: BeautifulSoup) -> str:
    candidates: list[str] = []
    for selector in ["[class*=descricao]", "[class*=description]", "section", "article"]:
        for tag in soup.select(selector):
            txt = _clean_text(tag.get_text(" ", strip=True))
            if len(txt) > 30:
                candidates.append(txt)
    if candidates:
        return max(candidates, key=len)[:2000]
    return _first_meta(soup, ["description", "og:description"])[:2000]


def _extract_product(url: str, config: CrawlConfig) -> dict[str, object] | None:
    try:
        html = _fetch(url)
    except Exception:
        return None

    soup = _soup(html)
    text = _clean_text(soup.get_text(" ", strip=True))
    title = _first_meta(soup, ["og:title", "twitter:title"])
    h1 = soup.find("h1")
    if h1:
        title = _clean_text(h1.get_text(" ", strip=True)) or title

    json_items = _extract_json_ld(soup)
    for item in json_items:
        if str(item.get("@type", "")).lower() == "product":
            title = _clean_text(item.get("name")) or title
            if not title:
                title = _clean_text(item.get("headline"))

    codigo = _extract_code(text, url)
    gtin = _extract_gtin(text)
    preco_venda, preco_custo = _extract_prices(text)
    estoque = _extract_stock(text, html, config)
    imagens = _extract_images(soup, url)
    categoria = _extract_category(soup)
    descricao_complementar = _extract_description(soup)

    if not title and not codigo:
        return None

    return {
        "Código": codigo or gtin,
        "Descrição": title or codigo,
        "Descrição complementar": descricao_complementar,
        "Unidade": "UN",
        "NCM": "",
        "GTIN/EAN": gtin,
        "Preço unitário": preco_venda,
        "Preço de custo": preco_custo,
        "Marca": "",
        "Categoria": categoria,
        "URL imagens externas": imagens,
        "Estoque": estoque,
        "Quantidade": estoque,
        "URL do produto": url,
        "Disponibilidade": "Esgotado" if estoque == 0 else "Em estoque",
        "Origem": "site",
    }


def crawl_site_to_bling_dataframe(raw_urls: str, estoque_padrao: int = 1) -> pd.DataFrame:
    start_urls = [_normalize_url(u) for u in re.split(r"[\n,;\s]+", str(raw_urls or "")) if str(u).strip()]
    if not start_urls:
        return pd.DataFrame()

    config = CrawlConfig(estoque_padrao=max(0, int(estoque_padrao or 0)))
    product_urls: list[str] = []
    for url in start_urls:
        if _is_product_url(url):
            product_urls.append(url)
    product_urls.extend(_discover_links(start_urls, config))

    ordered: list[str] = []
    seen: set[str] = set()
    for url in product_urls:
        normalized = _normalize_url(url)
        if normalized not in seen:
            seen.add(normalized)
            ordered.append(normalized)

    rows: list[dict[str, object]] = []
    for product_url in ordered[: config.max_products]:
        item = _extract_product(product_url, config)
        if item:
            rows.append(item)

    return pd.DataFrame(rows).fillna("")
