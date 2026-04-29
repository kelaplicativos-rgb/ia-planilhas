# bling_app_zero/core/site_crawler.py

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional
from urllib.parse import urljoin, urlparse, urldefrag

import pandas as pd
import requests
from bs4 import BeautifulSoup


BLOCKED_URL_PARTS = [
    "carrinho",
    "cart",
    "checkout",
    "login",
    "minha-conta",
    "account",
    "wishlist",
    "favoritos",
    "javascript:",
    "mailto:",
    "tel:",
    "politica",
    "privacidade",
    "termos",
]


PRODUCT_HINTS = [
    "/produto",
    "/product",
    "/p/",
    "produto/",
]


CATEGORY_HINTS = [
    "/categoria",
    "/category",
    "/departamento",
    "/colecao",
    "/collections",
]


@dataclass
class CrawlConfig:
    max_urls: int = 250
    max_products: int = 300
    max_depth: int = 2
    timeout: int = 15
    sleep_seconds: float = 0.15


def normalize_url(url: str) -> str:
    url = urldefrag(url.strip())[0]
    return url.rstrip("/")


def same_domain(url: str, base_domain: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        return host == base_domain or host.endswith("." + base_domain)
    except Exception:
        return False


def is_blocked_url(url: str) -> bool:
    low = url.lower()
    return any(part in low for part in BLOCKED_URL_PARTS)


def looks_like_product_url(url: str) -> bool:
    low = url.lower()
    return any(hint in low for hint in PRODUCT_HINTS)


def looks_like_category_url(url: str) -> bool:
    low = url.lower()
    return any(hint in low for hint in CATEGORY_HINTS)


def fetch_html(url: str, timeout: int = 15) -> Optional[str]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code >= 400:
            return None
        return response.text
    except Exception:
        return None


def extract_links(html: str, base_url: str, base_domain: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []

    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        if not href:
            continue

        absolute = normalize_url(urljoin(base_url, href))

        if not absolute.startswith("http"):
            continue

        if not same_domain(absolute, base_domain):
            continue

        if is_blocked_url(absolute):
            continue

        if looks_like_product_url(absolute) or looks_like_category_url(absolute):
            links.append(absolute)

    return list(dict.fromkeys(links))


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def extract_price(text: str) -> str:
    match = re.search(r"R\$\s*([\d\.\,]+)", text)
    if not match:
        return ""

    value = match.group(1)
    value = value.replace(".", "").replace(",", ".")
    return value


def extract_product_from_html(url: str, html: str) -> Optional[Dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    text = clean_text(soup.get_text(" "))

    title = ""

    h1 = soup.find("h1")
    if h1:
        title = clean_text(h1.get_text(" "))

    if not title and soup.title:
        title = clean_text(soup.title.get_text(" "))

    price = ""

    meta_price = soup.find("meta", attrs={"property": "product:price:amount"})
    if meta_price and meta_price.get("content"):
        price = clean_text(meta_price.get("content", ""))

    if not price:
        price = extract_price(text)

    images: List[str] = []

    for img in soup.select("img[src]"):
        src = img.get("src", "").strip()
        if not src:
            continue

        img_url = urljoin(url, src)

        low = img_url.lower()
        if any(x in low for x in ["logo", "banner", "sprite", "placeholder"]):
            continue

        images.append(img_url)

    images = list(dict.fromkeys(images))[:10]

    if not title:
        return None

    if not price and not looks_like_product_url(url):
        return None

    availability = "0" if any(
        x in text.lower()
        for x in ["sem estoque", "indisponível", "indisponivel", "esgotado"]
    ) else ""

    return {
        "URL": url,
        "Descrição": title,
        "Preço": price,
        "Estoque": availability,
        "Imagens": "|".join(images),
    }


def crawl_site(
    start_url: str,
    config: Optional[CrawlConfig] = None,
    progress_callback: Optional[Callable[[int, str, int], None]] = None,
) -> pd.DataFrame:
    """
    Crawler seguro anti-loop.

    Retorna DataFrame com:
    - URL
    - Descrição
    - Preço
    - Estoque
    - Imagens
    """

    config = config or CrawlConfig()

    start_url = normalize_url(start_url)
    parsed = urlparse(start_url)
    base_domain = parsed.netloc.lower().replace("www.", "")

    queue: List[tuple[str, int]] = [(start_url, 0)]
    visited = set()
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
            progress_callback(
                percent,
                f"Lendo {current_url}",
                len(products),
            )

        html = fetch_html(current_url, timeout=config.timeout)

        if not html:
            continue

        product = extract_product_from_html(current_url, html)

        if product:
            products.append(product)

            if progress_callback:
                progress_callback(
                    percent,
                    f"Produto encontrado: {product.get('Descrição', '')[:80]}",
                    len(products),
                )

            continue

        links = extract_links(html, current_url, base_domain)

        for link in links:
            if link not in visited and len(queue) < config.max_urls:
                queue.append((link, depth + 1))

        time.sleep(config.sleep_seconds)

    if progress_callback:
        elapsed = int(time.time() - started_at)
        progress_callback(
            100,
            f"Busca finalizada em {elapsed}s com {len(products)} produto(s).",
            len(products),
        )

    return pd.DataFrame(products)


def buscar_produtos_site(url: str) -> pd.DataFrame:
    """
    Função simples para compatibilidade com chamadas antigas.
    """
    return crawl_site(url)
