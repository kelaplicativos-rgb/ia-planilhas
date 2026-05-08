from __future__ import annotations

import json
import re
from collections import Counter, deque
from dataclasses import dataclass
from typing import Iterable
from urllib.parse import urljoin, urlparse, urlunparse

import pandas as pd
import requests
from bs4 import BeautifulSoup, Tag

from bling_app_zero.core.column_contract import RequestedField, build_contract
from bling_app_zero.core.gtin import clean_gtin
from bling_app_zero.core.text import clean_cell, normalize_key
from bling_app_zero.engines.ai_scraper_assist import enrich_row_with_ai

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cache-Control': 'no-cache',
}

BAD_LINK_TERMS = [
    'facebook', 'instagram', 'youtube', 'whatsapp', 'mailto:', 'tel:', '/login', '/conta', '/account',
    '/checkout', '/carrinho', '/cart', '/politica', '/privacy', '/termos', '/blog', '/noticia', '/news',
]
PRODUCT_HINTS = ['/produto', '/produtos', '/product', '/products', '/p/', 'produto-', 'product-', 'sku=', 'cod=', 'codigo=', 'ref=']
OUT_STOCK_TERMS = ['sem estoque', 'indisponivel', 'indisponível', 'esgotado', 'fora de estoque', 'avise-me']
IN_STOCK_TERMS = ['comprar', 'adicionar ao carrinho', 'em estoque', 'disponível', 'disponivel']


@dataclass(frozen=True)
class ScrapedPage:
    url: str
    html: str
    soup: BeautifulSoup
    text: str


def split_urls(raw: str) -> list[str]:
    lines = re.split(r'[\n,;]+', str(raw or ''))
    return [line.strip() for line in lines if line.strip().startswith(('http://', 'https://'))]


def _normalize_url(url: str) -> str:
    parsed = urlparse(str(url or '').strip())
    if not parsed.scheme or not parsed.netloc:
        return ''
    clean = parsed._replace(fragment='')
    clean = clean._replace(path=re.sub(r'/+', '/', clean.path or '/'))
    return urlunparse(clean).rstrip('/')


def _base_domain(url: str) -> str:
    return urlparse(url).netloc.lower().replace('www.', '')


def _same_domain(url: str, base_domain: str) -> bool:
    host = urlparse(url).netloc.lower().replace('www.', '')
    return host == base_domain or host.endswith('.' + base_domain)


def _safe_get(url: str) -> str:
    try:
        response = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
        if response.status_code in {403, 406, 429}:
            alt = dict(HEADERS)
            alt['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36'
            response = requests.get(url, headers=alt, timeout=25, allow_redirects=True)
        response.raise_for_status()
        return response.text or ''
    except Exception:
        return ''


def _make_page(url: str) -> ScrapedPage | None:
    normalized = _normalize_url(url)
    if not normalized:
        return None
    html = _safe_get(normalized)
    if not html:
        return None
    soup = BeautifulSoup(html, 'html.parser')
    text = clean_cell(soup.get_text(' ', strip=True))
    return ScrapedPage(url=normalized, html=html, soup=soup, text=text)


def _allowed_link(url: str, base_domain: str) -> bool:
    low = url.lower()
    if not url.startswith(('http://', 'https://')):
        return False
    if not _same_domain(url, base_domain):
        return False
    if any(term in low for term in BAD_LINK_TERMS):
        return False
    if re.search(r'\.(jpg|jpeg|png|webp|gif|svg|css|js|pdf|zip|rar)(\?|$)', low):
        return False
    return True


def _is_product_like_url(url: str) -> bool:
    low = url.lower()
    return any(hint in low for hint in PRODUCT_HINTS)


def _is_product_like_page(page: ScrapedPage) -> bool:
    low_html = page.html.lower()
    low_text = normalize_key(page.text)
    score = 40 if _is_product_like_url(page.url) else 0
    if 'og:type' in low_html and 'product' in low_html:
        score += 40
    if 'application/ld+json' in low_html and 'product' in low_html:
        score += 40
    if any(term in low_text for term in ['comprar', 'adicionar ao carrinho', 'preco', 'preço', 'sku', 'referencia']):
        score += 35
    return score >= 45


def _extract_links(page: ScrapedPage) -> list[str]:
    base_domain = _base_domain(page.url)
    links: list[str] = []
    for node in page.soup.find_all(['a', 'link', 'area'], href=True):
        absolute = _normalize_url(urljoin(page.url, str(node.get('href') or '')))
        if absolute and _allowed_link(absolute, base_domain) and absolute not in links:
            links.append(absolute)
    return links


def discover_product_links(start_urls: list[str], max_pages: int = 250, max_products: int = 1000) -> list[str]:
    starts = [_normalize_url(url) for url in start_urls if _normalize_url(url)]
    queue: deque[str] = deque(starts)
    visited: set[str] = set()
    products: list[str] = []
    while queue and len(visited) < max_pages and len(products) < max_products:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)
        page = _make_page(url)
        if page is None:
            continue
        if _is_product_like_page(page) and url not in products:
            products.append(url)
            if len(products) >= max_products:
                break
        links = _extract_links(page)
        links = sorted(links, key=lambda item: 0 if _is_product_like_url(item) else 1)
        for link in links:
            if link in visited:
                continue
            if _is_product_like_url(link) and link not in products:
                products.append(link)
                if len(products) >= max_products:
                    break
            if len(queue) + len(visited) < max_pages:
                queue.append(link)
    if not products:
        products = starts[:max_products]
    return products[:max_products]


def _node_signature(node: Tag) -> str:
    classes = '.'.join(sorted(str(c) for c in node.get('class', []) if c))
    return f'{node.name}:{classes}'


def _score_repeating_node(node: Tag) -> int:
    text = clean_cell(node.get_text(' ', strip=True))
    if len(text) < 20:
        return 0
    links = node.find_all('a', href=True)
    images = node.find_all('img')
    score = 0
    if links:
        score += 20
    if images:
        score += 20
    if re.search(r'R\$\s*[0-9\.]+,[0-9]{2}|[0-9\.]+,[0-9]{2}', text):
        score += 35
    if any(term in normalize_key(text) for term in ['comprar', 'produto', 'preco', 'preço', 'sku', 'codigo']):
        score += 25
    return score


def _extract_repeating_cards(soup: BeautifulSoup) -> list[Tag]:
    candidates: list[Tag] = []
    for node in soup.find_all(['article', 'li', 'div', 'tr']):
        if not isinstance(node, Tag):
            continue
        score = _score_repeating_node(node)
        if score >= 40:
            candidates.append(node)
    signatures = Counter(_node_signature(node) for node in candidates)
    repeating = [sig for sig, count in signatures.items() if count >= 2]
    filtered = [node for node in candidates if _node_signature(node) in repeating] if repeating else candidates
    compact: list[Tag] = []
    seen_text: set[str] = set()
    for node in filtered:
        text = clean_cell(node.get_text(' ', strip=True))[:220]
        key = normalize_key(text)
        if not key or key in seen_text:
            continue
        seen_text.add(key)
        compact.append(node)
        if len(compact) >= 200:
            break
    return compact


def _jsonld_products(page: ScrapedPage) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for script in page.soup.find_all('script', type='application/ld+json'):
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
                offer = item.get('offers')
                if isinstance(offer, list):
                    offer = offer[0] if offer else {}
                offer = offer if isinstance(offer, dict) else {}
                rows.append({
                    'url': clean_cell(item.get('url') or page.url),
                    'codigo': clean_cell(item.get('sku') or item.get('mpn') or ''),
                    'gtin': clean_gtin(item.get('gtin') or item.get('gtin13') or item.get('gtin14') or ''),
                    'descricao': clean_cell(item.get('name') or ''),
                    'preco': clean_cell(offer.get('price') or ''),
                    'estoque': _availability_to_stock(clean_cell(offer.get('availability') or '')),
                    'imagem': _join_images(item.get('image')),
                    'marca': _brand_from_json(item.get('brand')),
                    'categoria': clean_cell(item.get('category') or ''),
                })
            for value in item.values():
                if isinstance(value, (dict, list)):
                    queue.append(value)
    return rows


def _brand_from_json(value: object) -> str:
    if isinstance(value, dict):
        return clean_cell(value.get('name') or '')
    return clean_cell(value or '')


def _join_images(value: object) -> str:
    if isinstance(value, list):
        parts = [clean_cell(item) for item in value if clean_cell(item)]
        return '|'.join(dict.fromkeys(parts))
    return clean_cell(value or '')


def _availability_to_stock(value: str) -> str:
    key = normalize_key(value)
    if 'outofstock' in key or any(normalize_key(term) in key for term in OUT_STOCK_TERMS):
        return '0'
    if 'instock' in key or any(normalize_key(term) in key for term in IN_STOCK_TERMS):
        return '1'
    return ''


def _text_price(text: str) -> str:
    match = re.search(r'R\$\s*([0-9\.]+,[0-9]{2})', text)
    if match:
        return match.group(1)
    match = re.search(r'\b([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})\b', text)
    return match.group(1) if match else ''


def _text_stock(text: str) -> str:
    for pattern in [r'(?:estoque|saldo|quantidade|qtd)\s*[:\-]?\s*(\d{1,6})', r'(?:restam|resta|apenas)\s*(\d{1,6})']:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(1)
    key = normalize_key(text)
    if any(normalize_key(term) in key for term in OUT_STOCK_TERMS):
        return '0'
    if any(normalize_key(term) in key for term in IN_STOCK_TERMS):
        return '1'
    return ''


def _text_code(text: str) -> str:
    match = re.search(r'(?:SKU|COD|CÓD|Código|Codigo|REF|Referência)[:\s#-]+([A-Za-z0-9._/-]+)', text, flags=re.I)
    return clean_cell(match.group(1)) if match else ''


def _text_gtin(text: str) -> str:
    match = re.search(r'(?:GTIN|EAN|Código de barras|Codigo de barras)[:\s#-]+([0-9 .-]{8,20})', text, flags=re.I)
    if match:
        return clean_gtin(match.group(1))
    match = re.search(r'\b(\d{8}|\d{12}|\d{13}|\d{14})\b', text)
    return clean_gtin(match.group(1)) if match else ''


def _node_image(node: Tag, base_url: str) -> str:
    urls: list[str] = []
    for img in node.find_all('img'):
        src = img.get('src') or img.get('data-src') or img.get('data-lazy') or img.get('data-original') or img.get('data-zoom-image')
        if src:
            urls.append(urljoin(base_url, str(src)))
    clean_urls: list[str] = []
    for url in urls:
        low = url.lower()
        if any(term in low for term in ['logo', 'sprite', 'placeholder', 'icon', 'whatsapp']):
            continue
        if url not in clean_urls:
            clean_urls.append(url)
    return '|'.join(clean_urls[:12])


def _node_link(node: Tag, base_url: str) -> str:
    link = node.find('a', href=True)
    if link:
        return _normalize_url(urljoin(base_url, str(link.get('href') or '')))
    return base_url


def _node_title(node: Tag) -> str:
    for selector in ['h1', 'h2', 'h3', '[itemprop=name]', '.name', '.nome', '.title', '.titulo', '.product-name']:
        found = node.select_one(selector)
        if found:
            text = clean_cell(found.get_text(' ', strip=True))
            if text:
                return text
    image = node.find('img')
    if image and image.get('alt'):
        return clean_cell(image.get('alt'))
    text = clean_cell(node.get_text(' ', strip=True))
    if not text:
        return ''
    price = _text_price(text)
    if price:
        text = text.replace(price, '')
    return clean_cell(text)[:180]


def _row_from_node(node: Tag, base_url: str) -> dict[str, str]:
    text = clean_cell(node.get_text(' ', strip=True))
    return {
        'url': _node_link(node, base_url),
        'codigo': _text_code(text),
        'gtin': _text_gtin(text),
        'descricao': _node_title(node),
        'preco': _text_price(text),
        'estoque': _text_stock(text),
        'imagem': _node_image(node, base_url),
        'marca': '',
        'categoria': '',
    }


def _page_single_product_row(page: ScrapedPage) -> dict[str, str]:
    meta_title = page.soup.find('meta', property='og:title')
    title = clean_cell(meta_title.get('content')) if meta_title and meta_title.get('content') else ''
    if not title:
        h1 = page.soup.find('h1')
        title = clean_cell(h1.get_text(' ', strip=True)) if h1 else ''
    if not title and page.soup.title:
        title = clean_cell(page.soup.title.get_text(' ', strip=True))
    meta_price = page.soup.find('meta', property='product:price:amount')
    price = clean_cell(meta_price.get('content')) if meta_price and meta_price.get('content') else _text_price(page.text)
    return {
        'url': page.url,
        'codigo': _text_code(page.text),
        'gtin': _text_gtin(page.text),
        'descricao': title,
        'preco': price,
        'estoque': _text_stock(page.text),
        'imagem': _node_image(page.soup, page.url),
        'marca': '',
        'categoria': '',
    }


def _generic_rows_from_page(page: ScrapedPage) -> list[dict[str, str]]:
    rows = _jsonld_products(page)
    cards = _extract_repeating_cards(page.soup)
    for card in cards:
        row = _row_from_node(card, page.url)
        if any(value for key, value in row.items() if key != 'url'):
            rows.append(row)
    if not rows or _is_product_like_page(page):
        rows.append(_page_single_product_row(page))
    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        key = normalize_key((row.get('url') or '') + '|' + (row.get('descricao') or '') + '|' + (row.get('codigo') or ''))
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def _map_generic_to_contract(row: dict[str, str], contract: list[RequestedField]) -> dict[str, str]:
    out: dict[str, str] = {}
    for field in contract:
        kind = field.kind
        if kind == 'url':
            out[field.original] = row.get('url', '')
        elif kind in {'codigo', 'id_produto'}:
            out[field.original] = row.get('codigo', '')
        elif kind == 'gtin':
            out[field.original] = row.get('gtin', '')
        elif kind in {'descricao', 'nome_apoio'}:
            out[field.original] = row.get('descricao', '')
        elif kind in {'preco_unitario', 'preco_custo'}:
            out[field.original] = row.get('preco', '')
        elif kind == 'estoque':
            out[field.original] = row.get('estoque', '')
        elif kind == 'imagem':
            out[field.original] = row.get('imagem', '')
        elif kind == 'marca':
            out[field.original] = row.get('marca', '')
        elif kind == 'categoria':
            out[field.original] = row.get('categoria', '')
        elif kind == 'deposito':
            out[field.original] = ''
        else:
            out[field.original] = ''
    return out


def _ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for column in columns:
        if column not in out.columns:
            out[column] = ''
    return out.loc[:, columns].fillna('')


def _has_missing_requested_value(row: dict[str, str], contract: list[RequestedField]) -> bool:
    return any(not str(row.get(field.original, '')).strip() for field in contract)


def run_instant_scraper(
    raw_urls: str,
    requested_columns: Iterable[str] | None = None,
    operation: str = 'cadastro',
    all_products: bool = True,
    max_pages: int = 250,
    max_products: int = 1000,
    keep_only_requested_columns: bool = True,
) -> pd.DataFrame:
    start_urls = split_urls(raw_urls)
    contract = build_contract(requested_columns or [])
    if not start_urls:
        return pd.DataFrame(columns=[field.original for field in contract])
    urls = discover_product_links(start_urls, max_pages=max_pages, max_products=max_products) if all_products else start_urls
    rows: list[dict[str, str]] = []
    for url in urls[:max_products]:
        page = _make_page(url)
        if page is None:
            continue
        generic_rows = _generic_rows_from_page(page)
        for generic in generic_rows:
            if contract:
                row = _map_generic_to_contract(generic, contract)
                if _has_missing_requested_value(row, contract):
                    row = enrich_row_with_ai(
                        current_row=row,
                        contract=contract,
                        page_url=generic.get('url') or page.url,
                        page_text=page.text,
                        operation=operation,
                    )
                rows.append(row)
            else:
                rows.append({
                    'URL': generic.get('url', ''),
                    'Código': generic.get('codigo', ''),
                    'SKU': generic.get('codigo', ''),
                    'GTIN': generic.get('gtin', ''),
                    'Descrição': generic.get('descricao', ''),
                    'Nome': generic.get('descricao', ''),
                    'Preço': generic.get('preco', ''),
                    'Preço unitário (OBRIGATÓRIO)': generic.get('preco', ''),
                    'Estoque': generic.get('estoque', ''),
                    'Balanço (OBRIGATÓRIO)': generic.get('estoque', ''),
                    'URL Imagens': generic.get('imagem', ''),
                    'Imagens': generic.get('imagem', ''),
                    'Marca': generic.get('marca', ''),
                    'Categoria': generic.get('categoria', ''),
                })
            if len(rows) >= max_products:
                break
        if len(rows) >= max_products:
            break
    df = pd.DataFrame(rows).fillna('')
    if contract and keep_only_requested_columns:
        df = _ensure_columns(df, [field.original for field in contract])
    return df.fillna('')
