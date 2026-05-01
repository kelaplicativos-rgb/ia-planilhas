from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from typing import Callable
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
}

MAX_SITEMAPS = 18
MAX_SITEMAP_URLS = 6000
MAX_STOCK_PAGES = 450
TIMEOUT = 10

OUT_OF_STOCK_TERMS = (
    "sem estoque",
    "indisponivel",
    "indisponível",
    "esgotado",
    "produto esgotado",
    "fora de estoque",
    "estoque indisponivel",
    "estoque indisponível",
    "avise-me",
    "avise me",
    "produto indisponivel",
    "produto indisponível",
    "não disponível",
    "nao disponivel",
)

IN_STOCK_TERMS = (
    "em estoque",
    "disponivel",
    "disponível",
    "comprar",
    "adicionar ao carrinho",
    "pronta entrega",
    "produto disponível",
    "produto disponivel",
)

STOCK_COLUMNS_PRIORITY = (
    "Balanço (OBRIGATÓRIO)",
    "Balanco (OBRIGATORIO)",
    "Balanço",
    "Balanco",
    "Estoque",
    "Quantidade",
    "quantidade_real",
    "Disponibilidade",
)

PRODUCT_URL_COLUMNS = (
    "url_produto",
    "URL Produto",
    "URL do produto",
    "Link Produto",
    "Link do produto",
    "URL",
)


def _safe_df(df: object) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.copy().fillna("").reset_index(drop=True)
    return pd.DataFrame()


def _norm_url(url: object) -> str:
    texto = str(url or "").strip()
    if not texto:
        return ""
    if not texto.lower().startswith(("http://", "https://")):
        texto = "https://" + texto.lstrip("/")
    parsed = urlparse(texto)
    return parsed._replace(fragment="").geturl()


def _same_domain(a: str, b: str) -> bool:
    try:
        return urlparse(a).netloc.replace("www.", "").lower() == urlparse(b).netloc.replace("www.", "").lower()
    except Exception:
        return False


def _fetch_text(url: str) -> str:
    try:
        resp = requests.get(url, headers=REQUEST_HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.text or ""
    except Exception:
        return ""


def _robots_sitemaps(base_url: str) -> list[str]:
    parsed = urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    text = _fetch_text(robots_url)
    found: list[str] = []
    for line in text.splitlines():
        if line.lower().strip().startswith("sitemap:"):
            found.append(_norm_url(line.split(":", 1)[1].strip()))
    return found


def _candidate_sitemaps(base_url: str) -> list[str]:
    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    candidates = [
        f"{root}/sitemap.xml",
        f"{root}/sitemap_index.xml",
        f"{root}/sitemap-products.xml",
        f"{root}/product-sitemap.xml",
        f"{root}/products-sitemap.xml",
        f"{root}/sitemap_produtos.xml",
        f"{root}/sitemap-produtos.xml",
    ]
    candidates.extend(_robots_sitemaps(base_url))
    result: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        item = _norm_url(item)
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result[:MAX_SITEMAPS]


def _parse_xml_locs(xml_text: str) -> tuple[list[str], list[str]]:
    if not xml_text.strip():
        return [], []
    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except Exception:
        try:
            root = ET.fromstring(xml_text)
        except Exception:
            return [], []

    urls: list[str] = []
    sitemaps: list[str] = []
    for elem in root.iter():
        tag = elem.tag.split("}")[-1].lower()
        if tag != "loc" or not elem.text:
            continue
        loc = _norm_url(elem.text)
        if not loc:
            continue
        parent_hint = root.tag.split("}")[-1].lower()
        if loc.lower().endswith(".xml") or "sitemap" in loc.lower() or parent_hint == "sitemapindex":
            sitemaps.append(loc)
        else:
            urls.append(loc)
    return urls, sitemaps


def _discover_sitemap_urls(base_url: str, progress_callback: Callable[[int, str, int], None] | None = None, indice_url: int = 1) -> set[str]:
    queue = _candidate_sitemaps(base_url)
    visited: set[str] = set()
    urls: set[str] = set()

    while queue and len(visited) < MAX_SITEMAPS and len(urls) < MAX_SITEMAP_URLS:
        sitemap_url = queue.pop(0)
        if sitemap_url in visited:
            continue
        visited.add(sitemap_url)
        if progress_callback:
            progress_callback(95, f"SITEMAP ESTOQUE: lendo sitemap {len(visited)}/{MAX_SITEMAPS}", indice_url)
        text = _fetch_text(sitemap_url)
        page_urls, nested = _parse_xml_locs(text)
        for item in nested:
            if item not in visited and len(visited) + len(queue) < MAX_SITEMAPS:
                queue.append(item)
        for item in page_urls:
            if _same_domain(item, base_url):
                urls.add(item)
            if len(urls) >= MAX_SITEMAP_URLS:
                break

    return urls


def _url_col(df: pd.DataFrame) -> str:
    cols = {str(c).strip().lower(): str(c) for c in df.columns}
    for name in PRODUCT_URL_COLUMNS:
        found = cols.get(name.lower())
        if found:
            return found
    for col in df.columns:
        c = str(col).strip().lower()
        if "url" in c and ("produto" in c or "product" in c or c == "url"):
            return str(col)
    return ""


def _stock_col(df: pd.DataFrame) -> str:
    cols = {str(c).strip().lower(): str(c) for c in df.columns}
    for name in STOCK_COLUMNS_PRIORITY:
        found = cols.get(name.lower())
        if found:
            return found
    for col in df.columns:
        c = str(col).strip().lower()
        if any(token in c for token in ("balanço", "balanco", "estoque", "quantidade", "stock")):
            return str(col)
    return ""


def _extract_jsonld_availability(soup: BeautifulSoup) -> str:
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
            offers = obj.get("offers")
            if isinstance(offers, list):
                stack.extend([o for o in offers if isinstance(o, dict)])
                continue
            if isinstance(offers, dict):
                availability = str(offers.get("availability") or "")
                if availability:
                    return availability.lower()
            availability = str(obj.get("availability") or "")
            if availability:
                return availability.lower()
    return ""


def _detect_stock_from_html(html: str) -> tuple[str, str]:
    """Retorna apenas quantidade real ou indisponibilidade clara.

    Disponível/comprar não é estoque real. Isso não pode virar 1 nem acionar a
    mensagem de estoque real detectado, porque só confirma disponibilidade genérica.
    """
    if not html:
        return "", "sem_html"
    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.get_text(" ", strip=True).split()).lower()
    availability = _extract_jsonld_availability(soup)
    combined = f"{availability} {text}"

    quantity_patterns = (
        r"(\d{1,5})\s*(?:unidades|unidade|itens|item)\s*(?:em\s*)?estoque",
        r"estoque\s*[:#-]?\s*(\d{1,5})",
        r"saldo\s*[:#-]?\s*(\d{1,5})",
    )
    for pattern in quantity_patterns:
        match = re.search(pattern, combined, flags=re.I)
        if match:
            try:
                qty = int(match.group(1))
                return str(max(qty, 0)), "quantidade_texto"
            except Exception:
                pass

    if any(term in combined for term in OUT_OF_STOCK_TERMS) or "outofstock" in combined or "out_of_stock" in combined:
        return "0", "sem_estoque"

    if any(term in combined for term in IN_STOCK_TERMS) or "instock" in combined or "in_stock" in combined:
        return "", "disponivel_sem_quantidade"

    return "", "indefinido"


def _product_urls_from_df(df: pd.DataFrame) -> list[str]:
    col = _url_col(df)
    if not col:
        return []
    urls: list[str] = []
    seen: set[str] = set()
    for value in df[col].astype(str).tolist():
        url = _norm_url(value)
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def enrich_stock_from_sitemaps(
    df: pd.DataFrame,
    base_urls: list[str] | None = None,
    progress_callback: Callable[[int, str, int], None] | None = None,
    indice_url: int = 1,
) -> pd.DataFrame:
    """Reconsulta páginas de produtos detectadas usando sitemaps como índice.

    Não inventa quantidade. Se encontrar número explícito, usa esse número. Se
    encontrar indisponível/esgotado, usa 0. Se encontrar apenas disponível/comprar,
    registra status auxiliar, mas NÃO altera o balanço como estoque real.
    """
    base = _safe_df(df)
    if base.empty:
        return pd.DataFrame()

    url_col = _url_col(base)
    stock_col = _stock_col(base)
    if not url_col:
        return base
    if not stock_col:
        base["Balanço (OBRIGATÓRIO)"] = ""
        stock_col = "Balanço (OBRIGATÓRIO)"

    roots = [_norm_url(u) for u in (base_urls or []) if _norm_url(u)]
    if not roots:
        roots = sorted({f"{urlparse(_norm_url(u)).scheme}://{urlparse(_norm_url(u)).netloc}" for u in base[url_col].astype(str).tolist() if _norm_url(u)})

    sitemap_urls: set[str] = set()
    for root in roots[:3]:
        sitemap_urls.update(_discover_sitemap_urls(root, progress_callback=progress_callback, indice_url=indice_url))

    detected_urls = _product_urls_from_df(base)
    sitemap_lookup = {u.rstrip("/"): u for u in sitemap_urls}
    urls_to_check: list[str] = []
    for url in detected_urls:
        key = url.rstrip("/")
        urls_to_check.append(sitemap_lookup.get(key, url))

    urls_to_check = urls_to_check[:MAX_STOCK_PAGES]
    if not urls_to_check:
        return base

    estoque_por_url: dict[str, tuple[str, str]] = {}
    total = max(1, len(urls_to_check))
    for pos, product_url in enumerate(urls_to_check, start=1):
        if progress_callback and (pos == 1 or pos % 15 == 0 or pos == total):
            progress_callback(96, f"SITEMAP ESTOQUE: verificando estoque real {pos}/{total}", indice_url)
        html = _fetch_text(product_url)
        estoque_por_url[product_url.rstrip("/")] = _detect_stock_from_html(html)

    base["origem_estoque_real"] = ""
    base["status_estoque_site"] = ""
    alterados = 0
    status_detectados = 0
    for idx, row in base.iterrows():
        raw_url = _norm_url(row.get(url_col, "")).rstrip("/")
        sitemap_url = sitemap_lookup.get(raw_url, raw_url).rstrip("/")
        qty, status = estoque_por_url.get(sitemap_url, ("", ""))
        if status:
            base.at[idx, "status_estoque_site"] = status
            status_detectados += 1
        if qty != "":
            base.at[idx, stock_col] = qty
            base.at[idx, "origem_estoque_real"] = f"sitemap_html:{status}"
            alterados += 1

    if progress_callback:
        progress_callback(97, f"SITEMAP ESTOQUE: {alterados} item(ns) com quantidade real/zero explícito; {status_detectados} status lido(s)", indice_url)

    return base.fillna("")


__all__ = ["enrich_stock_from_sitemaps"]
