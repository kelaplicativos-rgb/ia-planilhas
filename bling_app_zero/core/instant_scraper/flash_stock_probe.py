from __future__ import annotations

import json
import re
import time
from html import unescape
from typing import Any
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
    "Cache-Control": "no-cache",
}

SEM_ESTOQUE_HINTS = (
    "sem estoque",
    "indisponível",
    "indisponivel",
    "esgotado",
    "fora de estoque",
    "produto esgotado",
    "avise-me",
    "avise me",
    "não disponível",
    "nao disponivel",
)

COM_ESTOQUE_HINTS = (
    "em estoque",
    "disponível",
    "disponivel",
    "comprar",
    "adicionar ao carrinho",
    "adicionar no carrinho",
    "add to cart",
    "comprar agora",
)

BAD_LINK_HINTS = (
    "login",
    "conta",
    "account",
    "carrinho",
    "cart",
    "checkout",
    "whatsapp",
    "facebook",
    "instagram",
    "youtube",
    "politica",
    "termos",
    "privacy",
    "blog",
    "faq",
    "atendimento",
    "contact",
    "contato",
)

STOCK_RE = re.compile(
    r"(?:estoque|dispon[ií]vel|quantidade|qtd|saldo)\D{0,35}(\d{1,5})|"
    r"(\d{1,5})\D{0,25}(?:unidades|pe[cç]as|itens)\D{0,25}(?:em estoque|dispon[ií]veis)",
    re.I,
)

FLASH_STOCK_MAX_PRODUCTS = 120
FLASH_STOCK_MAX_VALUE = 250
FLASH_STOCK_TIMEOUT = 12
FLASH_STOCK_DELAY_SECONDS = 0.12


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _norm(value: Any) -> str:
    text = _clean(value).lower()
    trans = str.maketrans("áàãâéêíóôõúç", "aaaaeeiooouc")
    return re.sub(r"[^a-z0-9]+", " ", text.translate(trans)).strip()


def _page_text(html: str) -> str:
    try:
        soup = BeautifulSoup(html or "", "html.parser")
        return " ".join(unescape(soup.get_text(" ", strip=True)).split())
    except Exception:
        return ""


def _fetch_html(url: str) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=FLASH_STOCK_TIMEOUT)
        resp.raise_for_status()
        return resp.text or ""
    except Exception:
        return ""


def _same_domain_or_relative(href: str, base_url: str) -> bool:
    try:
        parsed = urlparse(href)
        if not parsed.netloc:
            return True
        return parsed.netloc.replace("www.", "") == urlparse(base_url).netloc.replace("www.", "")
    except Exception:
        return True


def _is_product_link(href: str, base_url: str = "") -> bool:
    h = (href or "").lower().strip()
    if not h or h.startswith("#") or h.startswith("javascript:") or h.startswith("mailto:") or h.startswith("tel:"):
        return False
    if any(bad in h for bad in BAD_LINK_HINTS):
        return False
    if base_url and not _same_domain_or_relative(href, base_url):
        return False
    return any(x in h for x in ("produto", "product", "/p/", "/prod/", "/item/", "-p-", "sku", "products/")) or len(h.strip("/")) > 10


def _parse_jsonld_stock(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html or "", "html.parser")
    for script in soup.find_all("script", type=lambda x: x and "ld+json" in str(x).lower()):
        raw = script.string or script.get_text("", strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            obj = stack.pop(0)
            if isinstance(obj, list):
                stack.extend(obj)
                continue
            if not isinstance(obj, dict):
                continue
            graph = obj.get("@graph")
            if isinstance(graph, list):
                stack.extend(graph)
            offers = obj.get("offers") or {}
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            if not isinstance(offers, dict):
                continue
            availability = _norm(offers.get("availability"))
            if "outofstock" in availability or "soldout" in availability:
                return "0", "jsonld_outofstock"
            if "instock" in availability or "limitedavailability" in availability:
                qtd = offers.get("inventoryLevel") or ""
                if isinstance(qtd, dict):
                    qtd = qtd.get("value") or qtd.get("amount") or ""
                if str(qtd).isdigit():
                    return str(min(int(qtd), FLASH_STOCK_MAX_VALUE)), "jsonld_inventory"
                return "1", "jsonld_instock_minimo"
    return "", ""


def probe_stock_from_product_url(url: str) -> tuple[str, str]:
    html = _fetch_html(url)
    if not html:
        return "", "html_vazio"

    jsonld_stock, jsonld_source = _parse_jsonld_stock(html)
    if jsonld_source:
        return jsonld_stock, jsonld_source

    text = _page_text(html)
    norm_text = _norm(text)
    if not norm_text:
        return "", "sem_texto"

    if any(_norm(h) in norm_text for h in SEM_ESTOQUE_HINTS):
        return "0", "texto_sem_estoque"

    m = STOCK_RE.search(text)
    if m:
        value = next((x for x in m.groups() if x), "")
        if str(value).isdigit():
            return str(min(int(value), FLASH_STOCK_MAX_VALUE)), "texto_quantidade"

    if any(_norm(h) in norm_text for h in COM_ESTOQUE_HINTS):
        return "1", "texto_com_estoque_minimo"

    return "", "nao_detectado"


def enrich_dataframe_with_real_stock(
    df: pd.DataFrame,
    origem_url: str,
    progress_callback=None,
    indice_url: int = 1,
    max_products: int = FLASH_STOCK_MAX_PRODUCTS,
) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty or "url_produto" not in df.columns:
        return df

    base = df.copy().fillna("")
    max_products = max(1, min(int(max_products or FLASH_STOCK_MAX_PRODUCTS), FLASH_STOCK_MAX_PRODUCTS))

    urls: list[str] = []
    for raw in base["url_produto"].astype(str).tolist():
        product_url = urljoin(origem_url, _clean(raw))
        if _is_product_link(product_url, origem_url) and product_url not in urls:
            urls.append(product_url)
        if len(urls) >= max_products:
            break

    if not urls:
        base["Estoque real"] = ""
        base["origem_estoque_real"] = "sem_url_produto"
        return base

    total = len(urls)
    stock_by_url: dict[str, tuple[str, str]] = {}

    for i, product_url in enumerate(urls, start=1):
        if progress_callback and (i == 1 or i % 5 == 0 or i == total):
            pct = min(98, 72 + int((i / max(1, total)) * 24))
            progress_callback(pct, f"FLASH POINT HARD CORE: simulando estoque real {i}/{total}", indice_url)

        stock, source = probe_stock_from_product_url(product_url)
        stock_by_url[product_url] = (stock, source)
        time.sleep(FLASH_STOCK_DELAY_SECONDS)

    stocks: list[str] = []
    sources: list[str] = []
    for raw in base["url_produto"].astype(str).tolist():
        product_url = urljoin(origem_url, _clean(raw))
        stock, source = stock_by_url.get(product_url, ("", "nao_testado"))
        stocks.append(stock)
        sources.append(source)

    base["Estoque real"] = stocks
    if "Quantidade" in base.columns:
        base["Quantidade"] = [stock if str(stock).strip() else old for stock, old in zip(stocks, base["Quantidade"].astype(str).tolist())]
    else:
        base["Quantidade"] = stocks
    base["origem_estoque_real"] = sources
    return base
