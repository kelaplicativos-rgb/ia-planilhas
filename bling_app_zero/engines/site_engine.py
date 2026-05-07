from __future__ import annotations

import json
import re
from collections import deque
from datetime import date
from typing import Callable, Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

from bling_app_zero.core.column_contract import RequestedField, build_contract
from bling_app_zero.core.gtin import clean_gtin
from bling_app_zero.core.text import clean_cell, normalize_key

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (compatible; IA-Planilhas-Bling/3.1; +https://github.com/kelaplicativos-rgb/ia-planilhas)'
}

PRODUCT_HINTS = [
    '/produto', '/produtos', '/product', '/products', '/p/', '/item', '/loja/produto',
    'produto-', 'product-', 'sku=', 'variant=', 'ref=', 'cod=', 'codigo=',
]

BLOCKED_HINTS = [
    'facebook', 'instagram', 'whatsapp', 'youtube', 'mailto:', 'tel:', '#',
    '/login', '/conta', '/account', '/carrinho', '/cart', '/checkout', '/politica',
    '/privacy', '/termos', '/blog', '/noticia', '/news', '/institucional',
]

XML_FEED_HINTS = [
    '/feed', '/feeds', '/xml', '/produto.xml', '/produtos.xml', '/products.xml',
    '/google.xml', '/merchant.xml', '/facebook.xml', '/catalog.xml', '/catalogo.xml',
]


def split_urls(raw: str) -> list[str]:
    lines = re.split(r'[\n,;]+', str(raw or ''))
    return [line.strip() for line in lines if line.strip().startswith(('http://', 'https://'))]


def _normalize_url(url: str) -> str:
    parsed = urlparse(str(url or '').strip())
    if not parsed.scheme or not parsed.netloc:
        return ''
    path = re.sub(r'/+', '/', parsed.path or '/')
    clean = parsed._replace(path=path, fragment='')
    return urlunparse(clean).rstrip('/')


def _same_domain(url: str, base_domain: str) -> bool:
    host = urlparse(url).netloc.lower().replace('www.', '')
    return host == base_domain or host.endswith('.' + base_domain)


def _base_domain(url: str) -> str:
    return urlparse(url).netloc.lower().replace('www.', '')


def _root_url(url: str) -> str:
    parsed = urlparse(url)
    return f'{parsed.scheme}://{parsed.netloc}'


def _safe_get(url: str) -> str:
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        return response.text or ''
    except Exception:
        return ''


def _make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or '', 'html.parser')


def _page_text(soup: BeautifulSoup) -> str:
    return clean_cell(soup.get_text(' ', strip=True))


def _title(soup: BeautifulSoup, page_text: str = '') -> str:
    og = soup.find('meta', property='og:title')
    if og and og.get('content'):
        return clean_cell(og.get('content'))
    if soup.title and soup.title.string:
        return clean_cell(soup.title.string)
    h1 = soup.find('h1')
    return clean_cell(h1.get_text(' ', strip=True)) if h1 else ''


def _price(soup: BeautifulSoup, page_text: str) -> str:
    meta = soup.find('meta', property='product:price:amount')
    if meta and meta.get('content'):
        return clean_cell(meta.get('content'))
    for selector in ['[itemprop=price]', '.price', '.preco', '.valor', '.product-price']:
        node = soup.select_one(selector)
        if node:
            found = re.search(r'([0-9\.]+,[0-9]{2})', node.get_text(' ', strip=True))
            if found:
                return found.group(1)
    match = re.search(r'R\$\s*([0-9\.]+,[0-9]{2})', page_text)
    return match.group(1) if match else ''


def _images(soup: BeautifulSoup, page_text: str = '') -> str:
    urls: list[str] = []
    for meta in soup.find_all('meta'):
        prop = str(meta.get('property') or meta.get('name') or '').lower()
        if 'image' in prop and meta.get('content'):
            urls.append(str(meta.get('content')))
    for img in soup.find_all('img'):
        src = img.get('src') or img.get('data-src') or img.get('data-lazy') or img.get('data-original')
        if src:
            urls.append(str(src))
    cleaned: list[str] = []
    for raw_url in urls:
        image_url = raw_url.strip()
        low = image_url.lower()
        if not image_url or any(bad in low for bad in ['logo', 'sprite', 'placeholder', 'whatsapp', 'facebook', 'icon']):
            continue
        if image_url not in cleaned:
            cleaned.append(image_url)
        if len(cleaned) >= 12:
            break
    return '|'.join(cleaned)


def _stock(soup: BeautifulSoup, page_text: str) -> str:
    key = normalize_key(page_text)
    if any(term in key for term in ['sem estoque', 'indisponivel', 'esgotado', 'fora de estoque']):
        return '0'
    if any(term in key for term in ['comprar', 'adicionar ao carrinho', 'em estoque', 'disponivel']):
        return '1'
    return ''


def _sku(soup: BeautifulSoup, page_text: str) -> str:
    patterns = [
        r'(?:SKU|COD|CÓD|REF|REFERÊNCIA)[:\s#-]+([A-Za-z0-9._/-]+)',
        r'(?:Código|Codigo)[:\s#-]+([A-Za-z0-9._/-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, page_text, flags=re.I)
        if match:
            return clean_cell(match.group(1))
    return ''


def _gtin(soup: BeautifulSoup, page_text: str) -> str:
    patterns = [
        r'(?:GTIN|EAN|Código de barras|Codigo de barras|Barcode)[:\s#-]+([0-9 .-]{8,20})',
        r'\b(\d{8}|\d{12}|\d{13}|\d{14})\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, page_text, flags=re.I)
        if match:
            value = clean_gtin(match.group(1))
            if value:
                return value
    return ''


def _brand(soup: BeautifulSoup, page_text: str) -> str:
    meta = soup.find('meta', property='product:brand') or soup.find('meta', attrs={'name': 'brand'})
    if meta and meta.get('content'):
        return clean_cell(meta.get('content'))
    match = re.search(r'(?:Marca|Brand)[:\s-]+([A-Za-z0-9 Á-ú._/-]{2,40})', page_text, flags=re.I)
    return clean_cell(match.group(1)) if match else ''


def _category(soup: BeautifulSoup, page_text: str) -> str:
    for selector in ['breadcrumb', 'breadcrumbs']:
        for item in soup.find_all(class_=lambda value: value and selector in str(value).lower()):
            text = clean_cell(item.get_text(' > ', strip=True))
            if text:
                return text
    meta = soup.find('meta', property='product:category')
    return clean_cell(meta.get('content')) if meta and meta.get('content') else ''


def _empty_value(soup: BeautifulSoup, page_text: str) -> str:
    return ''


def _today_value(soup: BeautifulSoup, page_text: str) -> str:
    return date.today().isoformat()


def _jsonld_product_score(soup: BeautifulSoup) -> int:
    score = 0
    for script in soup.find_all('script', type='application/ld+json'):
        raw = script.string or script.get_text() or ''
        try:
            data = json.loads(raw)
        except Exception:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            text = json.dumps(item, ensure_ascii=False).lower()
            if 'product' in text:
                score += 70
            if 'offers' in text:
                score += 20
    return score


def _is_product_like(url: str, html: str = '') -> bool:
    low_url = url.lower()
    score = 45 if any(hint in low_url for hint in PRODUCT_HINTS) else 0
    if html:
        soup = _make_soup(html)
        text = normalize_key(_page_text(soup))
        if 'og:type' in html.lower() and 'product' in html.lower():
            score += 30
        score += _jsonld_product_score(soup)
        if any(term in text for term in ['comprar', 'adicionar ao carrinho', 'preco', 'sku', 'referencia']):
            score += 35
    return score >= 45


def _is_allowed_link(url: str, base_domain: str) -> bool:
    low = url.lower()
    if not url.startswith(('http://', 'https://')):
        return False
    if not _same_domain(url, base_domain):
        return False
    if any(bad in low for bad in BLOCKED_HINTS):
        return False
    if re.search(r'\.(jpg|jpeg|png|webp|gif|pdf|zip|rar|css|js|svg)(\?|$)', low):
        return False
    return True


def _extract_links(url: str, soup: BeautifulSoup, base_domain: str) -> list[str]:
    found: list[str] = []
    for node in soup.find_all(['a', 'link', 'area'], href=True):
        absolute = _normalize_url(urljoin(url, str(node.get('href'))))
        if absolute and _is_allowed_link(absolute, base_domain) and absolute not in found:
            found.append(absolute)
    return found


def _pagination_links(url: str, base_domain: str, page: int) -> list[str]:
    candidates: list[str] = []
    for token in [f'?page={page}', f'?pagina={page}', f'?p={page}', f'/page/{page}']:
        if token.startswith('?'):
            sep = '&' if '?' in url else '?'
            candidates.append(_normalize_url(url + sep + token[1:]))
        else:
            candidates.append(_normalize_url(url.rstrip('/') + token))
    return [item for item in candidates if item and _is_allowed_link(item, base_domain)]


def _xml_candidates(start_url: str) -> list[str]:
    root = _root_url(start_url)
    candidates = [
        f'{root}/sitemap.xml', f'{root}/sitemap_index.xml', f'{root}/sitemap-products.xml',
        f'{root}/product-sitemap.xml', f'{root}/products_sitemap.xml', f'{root}/produtos.xml',
        f'{root}/products.xml', f'{root}/google.xml', f'{root}/merchant.xml', f'{root}/facebook.xml',
        f'{root}/catalog.xml', f'{root}/catalogo.xml', f'{root}/feed.xml',
    ]
    robots = _safe_get(f'{root}/robots.txt')
    for match in re.findall(r'(?im)^\s*Sitemap:\s*(\S+)\s*$', robots or ''):
        normalized = _normalize_url(match)
        if normalized and normalized not in candidates:
            candidates.append(normalized)
    return candidates


def _parse_xml_urls(xml_text: str) -> list[str]:
    urls = re.findall(r'<loc>\s*([^<]+?)\s*</loc>', xml_text, flags=re.I)
    urls += re.findall(r'<g:link>\s*([^<]+?)\s*</g:link>', xml_text, flags=re.I)
    urls += re.findall(r'<link>\s*([^<]+?)\s*</link>', xml_text, flags=re.I)
    return [_normalize_url(url) for url in urls if _normalize_url(url)]


def _discover_from_xml_complement(start_urls: list[str], already_found: list[str], max_products: int) -> list[str]:
    products = list(already_found)
    seen_xml: set[str] = set()
    queue: deque[str] = deque()
    for start in start_urls:
        queue.extend(_xml_candidates(start))

    while queue and len(products) < max_products:
        xml_url = _normalize_url(queue.popleft())
        if not xml_url or xml_url in seen_xml:
            continue
        seen_xml.add(xml_url)
        base_domain = _base_domain(xml_url)
        xml = _safe_get(xml_url)
        if not xml:
            continue
        for loc in _parse_xml_urls(xml):
            if not _is_allowed_link(loc, base_domain):
                continue
            low = loc.lower()
            if ('sitemap' in low or low.endswith('.xml') or any(hint in low for hint in XML_FEED_HINTS)) and loc not in seen_xml:
                queue.append(loc)
                continue
            if _is_product_like(loc) and loc not in products:
                products.append(loc)
                if len(products) >= max_products:
                    break
    return products


def _discover_from_site_navigation(start_urls: list[str], max_pages: int, max_products: int) -> list[str]:
    discovered: list[str] = []
    visited: set[str] = set()
    queue: deque[str] = deque(_normalize_url(url) for url in start_urls if _normalize_url(url))

    while queue and len(visited) < max_pages and len(discovered) < max_products:
        url = _normalize_url(queue.popleft())
        if not url or url in visited:
            continue
        visited.add(url)
        base_domain = _base_domain(url)
        html = _safe_get(url)
        if not html:
            continue
        soup = _make_soup(html)

        if _is_product_like(url, html) and url not in discovered:
            discovered.append(url)
            if len(discovered) >= max_products:
                break

        links = _extract_links(url, soup, base_domain)
        product_first = sorted(links, key=lambda item: 0 if _is_product_like(item) else 1)
        for link in product_first:
            if link in visited:
                continue
            if _is_product_like(link) and link not in discovered:
                discovered.append(link)
                if len(discovered) >= max_products:
                    break
            if len(visited) + len(queue) < max_pages:
                queue.append(link)

        for page in range(2, 8):
            for paged in _pagination_links(url, base_domain, page):
                if paged not in visited and len(visited) + len(queue) < max_pages:
                    queue.append(paged)
    return discovered


def discover_product_urls(start_urls: list[str], max_pages: int = 250, max_products: int = 1000) -> list[str]:
    normalized_starts = [_normalize_url(url) for url in start_urls]
    normalized_starts = [url for url in normalized_starts if url]
    if not normalized_starts:
        return []

    discovered = _discover_from_site_navigation(normalized_starts, max_pages=max_pages, max_products=max_products)
    if len(discovered) < max_products:
        discovered = _discover_from_xml_complement(normalized_starts, already_found=discovered, max_products=max_products)
    return discovered


EXTRACTORS_BY_KIND: dict[str, Callable[[BeautifulSoup, str], str]] = {
    'id_produto': _sku,
    'codigo': _sku,
    'gtin': _gtin,
    'descricao': _title,
    'deposito': _empty_value,
    'estoque': _stock,
    'preco_unitario': _price,
    'preco_custo': _price,
    'observacao': _empty_value,
    'data': _today_value,
    'url': _empty_value,
    'nome_apoio': _title,
    'imagem': _images,
    'marca': _brand,
    'categoria': _category,
    'ncm': _empty_value,
}


def _extract_by_contract(url: str, contract: list[RequestedField], soup: BeautifulSoup, page_text: str) -> dict[str, str]:
    row: dict[str, str] = {}
    for field in contract:
        if field.kind == 'url':
            row[field.original] = url
            continue
        extractor = EXTRACTORS_BY_KIND.get(field.kind, _empty_value)
        row[field.original] = extractor(soup, page_text)
    return row


def scrape_product(url: str, requested_columns: Iterable[str] | None = None) -> dict[str, str]:
    contract = build_contract(requested_columns or [])
    html = _safe_get(url)
    soup = _make_soup(html)
    page_text = _page_text(soup)

    if contract:
        return _extract_by_contract(url=url, contract=contract, soup=soup, page_text=page_text)

    title = _title(soup, page_text)
    price = _price(soup, page_text)
    stock = _stock(soup, page_text)
    sku = _sku(soup, page_text)
    images = _images(soup, page_text)

    return {
        'URL': url,
        'Código': sku,
        'SKU': sku,
        'GTIN': _gtin(soup, page_text),
        'Descrição': title,
        'Nome': title,
        'Preço': price,
        'Preço unitário (OBRIGATÓRIO)': price,
        'Estoque': stock,
        'Balanço (OBRIGATÓRIO)': stock,
        'URL Imagens': images,
        'Imagens': images,
        'Marca': _brand(soup, page_text),
        'Categoria': _category(soup, page_text),
    }


def scrape_urls(urls: list[str], requested_columns: Iterable[str] | None = None) -> pd.DataFrame:
    rows = [scrape_product(url, requested_columns=requested_columns) for url in urls]
    return pd.DataFrame(rows).fillna('')


def scrape_all_products(
    start_urls: list[str],
    requested_columns: Iterable[str] | None = None,
    max_pages: int = 250,
    max_products: int = 1000,
) -> tuple[pd.DataFrame, list[str]]:
    product_urls = discover_product_urls(start_urls=start_urls, max_pages=max_pages, max_products=max_products)
    rows = [scrape_product(url, requested_columns=requested_columns) for url in product_urls]
    return pd.DataFrame(rows).fillna(''), product_urls
