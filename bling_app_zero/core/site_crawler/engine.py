from __future__ import annotations

import re
import time
from typing import Callable, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import pandas as pd
from bs4 import BeautifulSoup

from .config import CrawlConfig
from .http_fetcher import fetch_html
from .link_extractor import extract_links, is_blocked_url, looks_like_product_url
from .utils import normalize_url


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _extract_price(text: str) -> str:
    match = re.search(r"R\$\s*([0-9\.\,]+)", text or "")
    if not match:
        return ""
    value = match.group(1)
    return value.replace(".", "").replace(",", ".")


def _extract_images(url: str, soup: BeautifulSoup) -> str:
    images: List[str] = []
    for img in soup.select("img[src], img[data-src]"):
        src = str(img.get("src") or img.get("data-src") or "").strip()
        if not src:
            continue
        img_url = urljoin(url, src)
        low = img_url.lower()
        if any(term in low for term in ["logo", "banner", "sprite", "placeholder", "whatsapp", "icon"]):
            continue
        images.append(img_url)
    return "|".join(list(dict.fromkeys(images))[:10])


def _extract_product_from_html(url: str, html: str) -> Optional[Dict[str, str]]:
    soup = BeautifulSoup(html or "", "html.parser")
    text = _clean_text(soup.get_text(" "))

    title = ""
    h1 = soup.find("h1")
    if h1:
        title = _clean_text(h1.get_text(" "))
    if not title and soup.title:
        title = _clean_text(soup.title.get_text(" "))

    price = ""
    meta_price = soup.find("meta", attrs={"property": "product:price:amount"})
    if meta_price and meta_price.get("content"):
        price = _clean_text(str(meta_price.get("content", "")))
    if not price:
        price = _extract_price(text)

    if not title:
        return None
    if not price and not looks_like_product_url(url):
        return None

    text_lower = text.lower()
    stock = "0" if any(term in text_lower for term in ["sem estoque", "indisponivel", "indisponível", "esgotado"]) else ""

    return {
        "URL": url,
        "Descrição": title,
        "Preço": price,
        "Estoque": stock,
        "Imagens": _extract_images(url, soup),
    }


def crawl_site(
    start_url: str,
    config: Optional[CrawlConfig] = None,
    progress_callback: Optional[Callable[[int, str, int], None]] = None,
) -> pd.DataFrame:
    config = config or CrawlConfig()
    start_url = normalize_url(start_url)
    parsed = urlparse(start_url)
    base_domain = parsed.netloc.lower().replace("www.", "")

    queue: List[tuple[str, int]] = [(start_url, 0)]
    visited: set[str] = set()
    products: List[Dict[str, str]] = []
    started_at = time.time()

    while queue:
        if len(visited) >= config.max_urls:
            break
        if len(products) >= config.max_products:
            break

        current_url, depth = queue.pop(0)
        current_url = normalize_url(current_url)

        if current_url in visited:
            continue
        if is_blocked_url(current_url):
            continue
        if depth > config.max_depth:
            continue

        visited.add(current_url)
        percent = min(95, 10 + int((len(visited) / max(config.max_urls, 1)) * 80))

        if progress_callback:
            progress_callback(percent, f"Lendo {current_url}", len(products))

        html = fetch_html(current_url, timeout=config.timeout)
        if not html:
            continue

        product = _extract_product_from_html(current_url, html)
        if product:
            products.append(product)
            if progress_callback:
                progress_callback(percent, f"Produto encontrado: {product.get('Descrição', '')[:80]}", len(products))
            continue

        links = extract_links(html, current_url, base_domain)
        for link in links:
            if link not in visited and len(queue) < config.max_urls:
                queue.append((link, depth + 1))

        time.sleep(config.sleep_seconds)

    if progress_callback:
        elapsed = int(time.time() - started_at)
        progress_callback(100, f"Busca finalizada em {elapsed}s com {len(products)} produto(s).", len(products))

    return pd.DataFrame(products)


def buscar_produtos_site(url: str) -> pd.DataFrame:
    return crawl_site(url)
