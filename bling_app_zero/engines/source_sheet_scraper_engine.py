from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag

from bling_app_zero.core.column_contract import RequestedField, build_contract
from bling_app_zero.core.gtin import clean_gtin
from bling_app_zero.core.text import clean_cell, normalize_key

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'no-cache',
}

COMMON_FEEDS = [
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
PRODUCT_HINTS = ['/produto', '/produtos', '/product', '/products', '/p/', '/item/', 'produto-', 'product-', 'sku=', 'cod=', 'codigo=', 'ref=']
BLOCKED_TERMS = ['facebook', 'instagram', 'youtube', 'whatsapp', 'mailto:', 'tel:', '/login', '/conta', '/checkout', '/cart', '/carrinho', '/blog', '/politica', '/termos']
OUT_STOCK_TERMS = ['sem estoque', 'indisponivel', 'indisponível', 'esgotado', 'fora de estoque', 'outofstock', 'out_of_stock']
IN_STOCK_TERMS = ['comprar', 'adicionar ao carrinho', 'em estoque', 'disponivel', 'disponível', 'instock', 'in_stock']
MAX_WORKERS = 16
MAX_DISCOVERY_PAGES = 80
MAX_FEEDS = 80


@dataclass(frozen=True)
class SourceProduct:
    url: str = ''
    codigo: str = ''
    gtin: str = ''
    descricao: str = ''
    preco: str = ''
    estoque: str = ''
    imagem: str = ''
    marca: str = ''
    categoria: str = ''


def split_urls(raw: str) -> list[str]:
    return [item.strip() for item in re.split(r'[\n,;]+', str(raw or '')) if item.strip().startswith(('http://', 'https://'))]


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


def _same_domain(url: str, base: str) -> bool:
    host = _domain(url)
    root = _domain(base)
    return host == root or host.endswith('.' + root)


def _get(url: str, timeout: int = 14) -> str:
    try:
        response = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if response.status_code in {403, 406, 429}:
            alt = dict(HEADERS)
            alt['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0 Safari/537.36'
            response = requests.get(url, headers=alt, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        return response.text or ''
    except Exception:
        return ''


def _allowed_url(url: str, base: str) -> bool:
    low = url.lower()
    return (
        url.startswith(('http://', 'https://'))
        and _same_domain(url, base)
        and not any(term in low for term in BLOCKED_TERMS)
        and not re.search(r'\.(jpg|jpeg|png|webp|gif|svg|css|js|pdf|zip|rar)(\?|$)', low)
    )


def _productish_url(url: str) -> bool:
    low = url.lower()
    return any(hint in low for hint in PRODUCT_HINTS)


def _xml_urls(raw: str) -> list[str]:
    urls = re.findall(r'<loc>\s*([^<]+?)\s*</loc>', raw or '', flags=re.I)
    urls += re.findall(r'<g:link>\s*([^<]+?)\s*</g:link>', raw or '', flags=re.I)
    urls += re.findall(r'<link>\s*([^<]+?)\s*</link>', raw or '', flags=re.I)
    return [_norm(url) for url in urls if _norm(url)]


def _robots_sitemaps(raw: str) -> list[str]:
    return [_norm(match) for match in re.findall(r'(?im)^\s*Sitemap:\s*(\S+)\s*$', raw or '') if _norm(match)]


def _feed_candidates(start: str) -> list[str]:
    root = _root(start)
    candidates = [f'{root}/{feed}' for feed in COMMON_FEEDS]
    robots = _get(f'{root}/robots.txt', timeout=10)
    for sitemap in _robots_sitemaps(robots):
        if sitemap not in candidates:
            candidates.append(sitemap)
    return candidates


def _discover_from_feeds(starts: list[str], max_products: int) -> list[str]:
    queue: list[str] = []
    for start in starts:
        queue.extend(_feed_candidates(start))

    seen_feeds: set[str] = set()
    products: list[str] = []

    while queue and len(seen_feeds) < MAX_FEEDS and len(products) < max_products:
        feed_url = queue.pop(0)
        if not feed_url or feed_url in seen_feeds:
            continue
        seen_feeds.add(feed_url)
        raw = _get(feed_url, timeout=12)
        if not raw:
            continue
        for loc in _xml_urls(raw):
            if not any(_same_domain(loc, start) for start in starts):
                continue
            low = loc.lower()
            if ('sitemap' in low or low.endswith('.xml')) and loc not in seen_feeds:
                queue.append(loc)
                continue
            if loc not in products:
                products.append(loc)
                if len(products) >= max_products:
                    break
    return products[:max_products]


def _discover_from_html(starts: list[str], max_pages: int, max_products: int) -> list[str]:
    queue: list[str] = list(starts)
    visited: set[str] = set()
    products: list[str] = []

    while queue and len(visited) < min(max_pages, MAX_DISCOVERY_PAGES) and len(products) < max_products:
        url = _norm(queue.pop(0))
        if not url or url in visited:
            continue
        visited.add(url)
        html = _get(url, timeout=12)
        if not html:
            continue
        if _productish_url(url) and url not in products:
            products.append(url)
        soup = BeautifulSoup(html, 'html.parser')
        links: list[str] = []
        for node in soup.find_all('a', href=True):
            href = _norm(urljoin(url, str(node.get('href') or '')))
            if href and _allowed_url(href, url) and href not in links:
                links.append(href)
        links = sorted(links, key=lambda item: 0 if _productish_url(item) else 1)
        for link in links:
            if _productish_url(link) and link not in products:
                products.append(link)
                if len(products) >= max_products:
                    break
            if link not in visited and len(queue) + len(visited) < min(max_pages, MAX_DISCOVERY_PAGES):
                queue.append(link)
    return products[:max_products]


def discover_product_urls(raw_urls: str, all_products: bool, max_pages: int, max_products: int) -> list[str]:
    starts = [_norm(url) for url in split_urls(raw_urls) if _norm(url)]
    if not starts:
        return []
    if not all_products:
        return starts[:max_products]

    urls: list[str] = []
    for url in _discover_from_feeds(starts, max_products=max_products):
        if url not in urls:
            urls.append(url)
    if len(urls) < max_products:
        for url in _discover_from_html(starts, max_pages=max_pages, max_products=max_products):
            if url not in urls:
                urls.append(url)
                if len(urls) >= max_products:
                    break
    return (urls or starts)[:max_products]


def _price(text: str) -> str:
    match = re.search(r'R\$\s*([0-9\.]+,[0-9]{2})', text)
    if match:
        return match.group(1)
    match = re.search(r'\b([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})\b', text)
    return match.group(1) if match else ''


def _stock(text: str) -> str:
    for pattern in [
        r'["\'](?:stock|estoque|inventory|quantity|qty|saldo|available_quantity)["\']\s*[:=]\s*["\']?(\d{1,7})',
        r'(?:estoque|saldo|quantidade|qtd)\s*[:\-]?\s*(\d{1,7})',
        r'(?:restam|resta|apenas)\s*(\d{1,7})',
    ]:
        match = re.search(pattern, text, flags=re.I)
        if match:
            digits = re.sub(r'\D+', '', match.group(1))
            return str(int(digits)) if digits else ''
    key = normalize_key(text)
    if any(normalize_key(term) in key for term in OUT_STOCK_TERMS):
        return '0'
    if any(normalize_key(term) in key for term in IN_STOCK_TERMS):
        return '1'
    return ''


def _code(text: str) -> str:
    match = re.search(r'(?:SKU|COD|CÓD|Código|Codigo|REF|Referência|Modelo)[:\s#-]+([A-Za-z0-9._/-]+)', text, flags=re.I)
    return clean_cell(match.group(1)) if match else ''


def _gtin(text: str) -> str:
    match = re.search(r'(?:GTIN|EAN|Código de barras|Codigo de barras)[:\s#-]+([0-9 .-]{8,20})', text, flags=re.I)
    if match:
        return clean_gtin(match.group(1))
    match = re.search(r'\b(\d{8}|\d{12}|\d{13}|\d{14})\b', text)
    return clean_gtin(match.group(1)) if match else ''


def _images(soup: BeautifulSoup, base_url: str) -> str:
    urls: list[str] = []
    for img in soup.find_all('img'):
        src = img.get('src') or img.get('data-src') or img.get('data-lazy') or img.get('data-original') or img.get('data-zoom-image')
        if not src:
            continue
        url = urljoin(base_url, str(src))
        low = url.lower()
        if any(term in low for term in ['logo', 'sprite', 'placeholder', 'icon', 'whatsapp']):
            continue
        if url not in urls:
            urls.append(url)
        if len(urls) >= 12:
            break
    return '|'.join(urls)


def _title(soup: BeautifulSoup) -> str:
    for selector in ['h1', '[itemprop=name]', '.product-name', '.nome', '.name', '.titulo', '.title']:
        node = soup.select_one(selector)
        if node:
            value = clean_cell(node.get_text(' ', strip=True))
            if value:
                return value[:240]
    meta = soup.find('meta', property='og:title')
    if meta and meta.get('content'):
        return clean_cell(meta.get('content'))[:240]
    if soup.title:
        return clean_cell(soup.title.get_text(' ', strip=True))[:240]
    return ''


def _brand_from_json(value: object) -> str:
    if isinstance(value, dict):
        return clean_cell(value.get('name') or '')
    return clean_cell(value or '')


def _jsonld_product(soup: BeautifulSoup, page_url: str) -> SourceProduct | None:
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
            type_text = str(item.get('@type') or item.get('type') or '').lower()
            if 'product' in type_text or ('offers' in item and 'name' in item):
                offers = item.get('offers')
                offer = offers[0] if isinstance(offers, list) and offers else offers
                offer = offer if isinstance(offer, dict) else {}
                image = item.get('image')
                if isinstance(image, list):
                    image_value = '|'.join(dict.fromkeys(clean_cell(x) for x in image if clean_cell(x)))
                else:
                    image_value = clean_cell(image or '')
                stock_value = ''
                availability = normalize_key(offer.get('availability', ''))
                if any(term in availability for term in OUT_STOCK_TERMS):
                    stock_value = '0'
                elif any(term in availability for term in IN_STOCK_TERMS):
                    stock_value = '1'
                return SourceProduct(
                    url=clean_cell(item.get('url') or page_url),
                    codigo=clean_cell(item.get('sku') or item.get('mpn') or ''),
                    gtin=clean_gtin(item.get('gtin') or item.get('gtin13') or item.get('gtin14') or ''),
                    descricao=clean_cell(item.get('name') or ''),
                    preco=clean_cell(offer.get('price') or ''),
                    estoque=stock_value,
                    imagem=image_value,
                    marca=_brand_from_json(item.get('brand')),
                    categoria=clean_cell(item.get('category') or ''),
                )
            for value in item.values():
                if isinstance(value, (dict, list)):
                    queue.append(value)
    return None


def _scrape_one(url: str) -> SourceProduct:
    html = _get(url, timeout=14)
    if not html:
        return SourceProduct(url=url)
    soup = BeautifulSoup(html, 'html.parser')
    text = clean_cell(soup.get_text(' ', strip=True))
    product = _jsonld_product(soup, url)
    if product is not None:
        fallback_stock = product.estoque or _stock(html + ' ' + text)
        fallback_image = product.imagem or _images(soup, url)
        return SourceProduct(
            url=product.url or url,
            codigo=product.codigo or _code(text),
            gtin=product.gtin or _gtin(text),
            descricao=product.descricao or _title(soup),
            preco=product.preco or _price(text),
            estoque=fallback_stock,
            imagem=fallback_image,
            marca=product.marca,
            categoria=product.categoria,
        )
    return SourceProduct(
        url=url,
        codigo=_code(text),
        gtin=_gtin(text),
        descricao=_title(soup),
        preco=_price(text),
        estoque=_stock(html + ' ' + text),
        imagem=_images(soup, url),
        marca='',
        categoria='',
    )


def _generic_to_contract(product: SourceProduct, contract: list[RequestedField]) -> dict[str, str]:
    row: dict[str, str] = {}
    for field in contract:
        kind = field.kind
        if kind == 'url':
            row[field.original] = product.url
        elif kind in {'codigo', 'id_produto'}:
            row[field.original] = product.codigo
        elif kind == 'gtin':
            row[field.original] = product.gtin
        elif kind in {'descricao', 'nome_apoio'}:
            row[field.original] = product.descricao
        elif kind in {'preco_unitario', 'preco_custo'}:
            row[field.original] = product.preco
        elif kind == 'estoque':
            row[field.original] = product.estoque
        elif kind == 'imagem':
            row[field.original] = product.imagem
        elif kind == 'marca':
            row[field.original] = product.marca
        elif kind == 'categoria':
            row[field.original] = product.categoria
        else:
            row[field.original] = ''
    return row


def _default_columns(operation: str) -> list[str]:
    if operation == 'estoque':
        return ['Código', 'Descrição', 'Depósito (OBRIGATÓRIO)', 'Balanço (OBRIGATÓRIO)']
    return ['URL', 'Código', 'SKU', 'GTIN', 'Descrição', 'Nome', 'Preço', 'Preço unitário (OBRIGATÓRIO)', 'URL Imagens', 'Imagens', 'Marca', 'Categoria']


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for column in columns:
        if column not in out.columns:
            out[column] = ''
    return out.loc[:, columns].fillna('')


def run_source_sheet_scraper(
    raw_urls: str,
    requested_columns: Iterable[str] | None = None,
    operation: str = 'cadastro',
    all_products: bool = True,
    max_pages: int = 120,
    max_products: int = 300,
    keep_only_requested_columns: bool = True,
) -> pd.DataFrame:
    columns = [str(column).strip() for column in (requested_columns or []) if str(column).strip()] or _default_columns(operation)
    contract = build_contract(columns)
    urls = discover_product_urls(raw_urls, all_products=all_products, max_pages=max_pages, max_products=max_products)
    if not urls:
        return pd.DataFrame(columns=columns)

    products: list[SourceProduct] = []
    with ThreadPoolExecutor(max_workers=max(1, min(MAX_WORKERS, len(urls)))) as executor:
        futures = [executor.submit(_scrape_one, url) for url in urls[:max_products]]
        for future in as_completed(futures):
            try:
                product = future.result()
                if any([product.codigo, product.descricao, product.preco, product.estoque, product.imagem, product.url]):
                    products.append(product)
            except Exception:
                continue

    rows = [_generic_to_contract(product, contract) for product in products]
    df = pd.DataFrame(rows).fillna('')
    if keep_only_requested_columns:
        df = _ensure_columns(df, columns)
    return df.fillna('')
