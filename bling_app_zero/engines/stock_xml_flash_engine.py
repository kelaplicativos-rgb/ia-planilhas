from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from bling_app_zero.core.column_contract import build_contract
from bling_app_zero.core.text import clean_cell, normalize_key

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'no-cache',
}

COMMON_XML_PATHS = [
    'robots.txt',
    'sitemap.xml',
    'sitemap_index.xml',
    'sitemap-products.xml',
    'product-sitemap.xml',
    'products-sitemap.xml',
    'produtos.xml',
    'products.xml',
    'google.xml',
    'merchant.xml',
    'facebook.xml',
    'catalog.xml',
    'catalogo.xml',
    'feed.xml',
]
OUT_TERMS = ['sem estoque', 'indisponivel', 'indisponível', 'esgotado', 'fora de estoque', 'outofstock', 'out_of_stock']
IN_TERMS = ['em estoque', 'disponivel', 'disponível', 'instock', 'in_stock', 'available', 'comprar']
MAX_XML_DOCS = 100
MAX_PRODUCT_URLS = 1800
MAX_WORKERS = 18
STRONG_MATCH_SCORE = 60


@dataclass(frozen=True)
class StockCandidate:
    url: str
    code: str
    name: str
    stock: str
    confidence: int


def _norm(url: str) -> str:
    parsed = urlparse(str(url or '').strip())
    if not parsed.scheme or not parsed.netloc:
        return ''
    clean = parsed._replace(fragment='', path=re.sub(r'/+', '/', parsed.path or '/'))
    return urlunparse(clean).rstrip('/')


def _root(url: str) -> str:
    parsed = urlparse(url)
    return f'{parsed.scheme}://{parsed.netloc}'


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().replace('www.', '')


def _same_domain(url: str, base_url: str) -> bool:
    host = _domain(url)
    base = _domain(base_url)
    return host == base or host.endswith('.' + base)


def _get(url: str) -> str:
    try:
        response = requests.get(url, headers=HEADERS, timeout=14, allow_redirects=True)
        response.raise_for_status()
        return response.text or ''
    except Exception:
        return ''


def _xml_urls(raw: str) -> list[str]:
    urls = re.findall(r'<loc>\s*([^<]+?)\s*</loc>', raw or '', flags=re.I)
    urls += re.findall(r'<g:link>\s*([^<]+?)\s*</g:link>', raw or '', flags=re.I)
    urls += re.findall(r'<link>\s*([^<]+?)\s*</link>', raw or '', flags=re.I)
    return [_norm(url) for url in urls if _norm(url)]


def _robots_sitemaps(raw: str) -> list[str]:
    return [_norm(match) for match in re.findall(r'(?im)^\s*Sitemap:\s*(\S+)\s*$', raw or '') if _norm(match)]


def _xml_candidates(start_url: str) -> list[str]:
    root = _root(start_url)
    candidates = [f'{root}/{path}' for path in COMMON_XML_PATHS]
    robots = _get(f'{root}/robots.txt')
    for url in _robots_sitemaps(robots):
        if url not in candidates:
            candidates.append(url)
    return candidates


def discover_product_urls_from_xml(start_urls: Iterable[str], max_products: int = MAX_PRODUCT_URLS) -> list[str]:
    starts = [_norm(url) for url in start_urls if _norm(url)]
    queue: list[str] = []
    for start in starts:
        queue.extend(_xml_candidates(start))
    seen_xml: set[str] = set()
    products: list[str] = []

    while queue and len(seen_xml) < MAX_XML_DOCS and len(products) < max_products:
        xml_url = queue.pop(0)
        if not xml_url or xml_url in seen_xml:
            continue
        seen_xml.add(xml_url)
        raw = _get(xml_url)
        if not raw:
            continue
        for loc in _xml_urls(raw):
            if not any(_same_domain(loc, start) for start in starts):
                continue
            low = loc.lower()
            if ('sitemap' in low or low.endswith('.xml')) and loc not in seen_xml:
                queue.append(loc)
                continue
            if loc not in products:
                products.append(loc)
                if len(products) >= max_products:
                    break
    return products[:max_products]


def _digits(value: object) -> str:
    digits = re.sub(r'\D+', '', str(value or ''))
    return str(int(digits)) if digits else ''


def _stock_from_jsonld(soup: BeautifulSoup) -> tuple[str, int]:
    for script in soup.find_all('script', type='application/ld+json'):
        raw = script.string or script.get_text() or ''
        try:
            data = json.loads(raw)
        except Exception:
            continue
        queue = data if isinstance(data, list) else [data]
        while queue:
            item = queue.pop(0)
            if isinstance(item, list):
                queue.extend(item)
                continue
            if not isinstance(item, dict):
                continue
            offers = item.get('offers')
            offers_list = offers if isinstance(offers, list) else [offers]
            for offer in offers_list:
                if not isinstance(offer, dict):
                    continue
                for key in ['inventoryLevel', 'quantity', 'stock', 'qty', 'availableQuantity']:
                    qty = _digits(offer.get(key))
                    if qty:
                        return qty, 95
                availability = normalize_key(offer.get('availability', ''))
                if any(term in availability for term in OUT_TERMS):
                    return '0', 90
                if any(term in availability for term in IN_TERMS):
                    return '1', 70
            for value in item.values():
                if isinstance(value, (dict, list)):
                    queue.append(value)
    return '', 0


def _stock_from_html(html: str, text: str) -> tuple[str, int]:
    for pattern in [
        r'["\'](?:stock|estoque|inventory|quantity|qty|saldo|available_quantity)["\']\s*[:=]\s*["\']?(\d{1,7})',
        r'(?:estoque|saldo|quantidade|qtd)\s*[:\-]?\s*(\d{1,7})',
        r'(?:restam|resta|apenas)\s*(\d{1,7})',
    ]:
        match = re.search(pattern, html + ' ' + text, flags=re.I)
        if match:
            return _digits(match.group(1)), 82
    key = normalize_key(text + ' ' + html[:5000])
    if any(normalize_key(term) in key for term in OUT_TERMS):
        return '0', 75
    if any(normalize_key(term) in key for term in IN_TERMS):
        return '1', 55
    return '', 0


def _code_from_text(text: str) -> str:
    match = re.search(r'(?:SKU|COD|CÓD|Código|Codigo|REF|Referência|Modelo)[:\s#-]+([A-Za-z0-9._/-]+)', text, flags=re.I)
    return clean_cell(match.group(1)) if match else ''


def _name_from_soup(soup: BeautifulSoup) -> str:
    for selector in ['h1', '[itemprop=name]', '.product-name', '.nome', '.name', '.titulo', '.title']:
        found = soup.select_one(selector)
        if found:
            value = clean_cell(found.get_text(' ', strip=True))
            if value:
                return value
    if soup.title:
        return clean_cell(soup.title.get_text(' ', strip=True))
    return ''


def _scan_one(url: str) -> StockCandidate:
    html = _get(url)
    if not html:
        return StockCandidate(url=url, code='', name='', stock='', confidence=0)
    soup = BeautifulSoup(html, 'html.parser')
    text = clean_cell(soup.get_text(' ', strip=True))
    stock, confidence = _stock_from_jsonld(soup)
    if not stock:
        stock, confidence = _stock_from_html(html, text)
    return StockCandidate(url=url, code=_code_from_text(text), name=_name_from_soup(soup), stock=stock, confidence=confidence)


def _best_match_stock(row: dict[str, str], candidates: list[StockCandidate]) -> tuple[str, int]:
    row_values = {normalize_key(key): normalize_key(value) for key, value in row.items() if str(value or '').strip()}
    row_url = row_values.get('url') or row_values.get('link') or ''
    row_code = row_values.get('codigo') or row_values.get('sku') or row_values.get('referencia') or ''
    row_name = row_values.get('descricao') or row_values.get('nome') or row_values.get('produto') or ''

    best_stock = ''
    best_score = 0
    for item in candidates:
        if not item.stock:
            continue
        score = 0
        item_url = normalize_key(item.url)
        item_code = normalize_key(item.code)
        item_name = normalize_key(item.name)
        if row_url and (row_url in item_url or item_url in row_url):
            score += 100
        if row_code and item_code and (row_code == item_code or row_code in item_code or item_code in row_code):
            score += 80
        if row_name and item_name:
            words = set(row_name.split()) & set(item_name.split())
            score += min(60, len(words) * 8)
        score += min(20, item.confidence // 5)
        if score > best_score:
            best_score = score
            best_stock = item.stock
    return best_stock, best_score


def contract_has_stock(columns: Iterable[str]) -> bool:
    return any(field.kind == 'estoque' for field in build_contract(columns))


def apply_flash_stock_complement(df: pd.DataFrame, raw_urls: str, requested_columns: Iterable[str]) -> pd.DataFrame:
    columns = [str(column).strip() for column in requested_columns if str(column).strip()]
    if not contract_has_stock(columns):
        return df
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame(columns=columns)

    stock_columns = [field.original for field in build_contract(columns) if field.kind == 'estoque']
    if not stock_columns:
        return df

    start_urls = [url for url in re.split(r'[\n,;]+', str(raw_urls or '')) if url.strip().startswith(('http://', 'https://'))]
    product_urls = discover_product_urls_from_xml(start_urls)
    if not product_urls:
        product_urls = start_urls

    candidates: list[StockCandidate] = []
    with ThreadPoolExecutor(max_workers=max(1, min(MAX_WORKERS, len(product_urls)))) as executor:
        futures = [executor.submit(_scan_one, url) for url in product_urls[:MAX_PRODUCT_URLS]]
        for future in as_completed(futures):
            try:
                item = future.result()
                if item.stock:
                    candidates.append(item)
            except Exception:
                continue

    if not candidates:
        return df

    out = df.copy().fillna('')
    for column in stock_columns:
        if column not in out.columns:
            out[column] = ''

    for idx, row in out.iterrows():
        row_dict = {str(k): str(v or '') for k, v in row.to_dict().items()}
        stock, score = _best_match_stock(row_dict, candidates)
        if not stock or score < STRONG_MATCH_SCORE:
            continue
        for column in stock_columns:
            out.at[idx, column] = stock

    for column in columns:
        if column not in out.columns:
            out[column] = ''
    return out.loc[:, columns].fillna('')
