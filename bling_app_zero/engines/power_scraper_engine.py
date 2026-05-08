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
PRODUCT_HINTS = ['/produto', '/produtos', '/product', '/products', '/p/', '/item/', 'produto-', 'product-', 'sku=', 'cod=', 'codigo=', 'ref=']
BLOCKED = ['facebook', 'instagram', 'youtube', 'whatsapp', 'mailto:', 'tel:', '/login', '/conta', '/checkout', '/cart', '/carrinho', '/blog', '/politica', '/termos']
OUT_STOCK = ['sem estoque', 'indisponivel', 'indisponível', 'esgotado', 'fora de estoque', 'avise-me']
IN_STOCK = ['comprar', 'adicionar ao carrinho', 'em estoque', 'disponivel', 'disponível']
COMMON_FEEDS = ['sitemap.xml', 'sitemap_index.xml', 'sitemap-products.xml', 'product-sitemap.xml', 'produtos.xml', 'products.xml', 'google.xml', 'merchant.xml', 'facebook.xml', 'catalog.xml', 'catalogo.xml', 'feed.xml']


@dataclass(frozen=True)
class Page:
    url: str
    html: str
    soup: BeautifulSoup
    text: str


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


def _same_domain(url: str, domain: str) -> bool:
    host = _domain(url)
    return host == domain or host.endswith('.' + domain)


def _get(url: str) -> str:
    try:
        session = requests.Session()
        response = session.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
        if response.status_code in {403, 406, 429}:
            alt = dict(HEADERS)
            alt['User-Agent'] = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/121.0 Safari/537.36'
            response = session.get(url, headers=alt, timeout=25, allow_redirects=True)
        response.raise_for_status()
        return response.text or ''
    except Exception:
        return ''


def _page(url: str) -> Page | None:
    url = _norm(url)
    if not url:
        return None
    html = _get(url)
    if not html:
        return None
    soup = BeautifulSoup(html, 'html.parser')
    return Page(url=url, html=html, soup=soup, text=clean_cell(soup.get_text(' ', strip=True)))


def _allowed(url: str, domain: str) -> bool:
    low = url.lower()
    return (
        url.startswith(('http://', 'https://'))
        and _same_domain(url, domain)
        and not any(bad in low for bad in BLOCKED)
        and not re.search(r'\.(jpg|jpeg|png|webp|gif|svg|css|js|pdf|zip|rar)(\?|$)', low)
    )


def _productish_url(url: str) -> bool:
    low = url.lower()
    return any(hint in low for hint in PRODUCT_HINTS)


def _productish_page(page: Page) -> bool:
    html = page.html.lower()
    text = normalize_key(page.text)
    score = 45 if _productish_url(page.url) else 0
    if 'og:type' in html and 'product' in html:
        score += 40
    if 'application/ld+json' in html and 'product' in html:
        score += 40
    if any(term in text for term in ['comprar', 'adicionar ao carrinho', 'preco', 'preço', 'sku', 'referencia']):
        score += 35
    return score >= 45


def _links(page: Page) -> list[str]:
    domain = _domain(page.url)
    found: list[str] = []
    for node in page.soup.find_all(['a', 'link', 'area'], href=True):
        url = _norm(urljoin(page.url, str(node.get('href') or '')))
        if url and _allowed(url, domain) and url not in found:
            found.append(url)
    return found


def _parse_xml_urls(xml: str) -> list[str]:
    urls = re.findall(r'<loc>\s*([^<]+?)\s*</loc>', xml, flags=re.I)
    urls += re.findall(r'<g:link>\s*([^<]+?)\s*</g:link>', xml, flags=re.I)
    urls += re.findall(r'<link>\s*([^<]+?)\s*</link>', xml, flags=re.I)
    return [_norm(url) for url in urls if _norm(url)]


def _feed_candidates(start_url: str) -> list[str]:
    root = _root(start_url)
    candidates = [f'{root}/{name}' for name in COMMON_FEEDS]
    robots = _get(f'{root}/robots.txt')
    for match in re.findall(r'(?im)^\s*Sitemap:\s*(\S+)\s*$', robots or ''):
        url = _norm(match)
        if url and url not in candidates:
            candidates.append(url)
    return candidates


def _discover_from_feeds(starts: list[str], limit: int) -> list[str]:
    products: list[str] = []
    queue: deque[str] = deque()
    seen: set[str] = set()
    for start in starts:
        queue.extend(_feed_candidates(start))
    while queue and len(products) < limit:
        url = _norm(queue.popleft())
        if not url or url in seen:
            continue
        seen.add(url)
        xml = _get(url)
        if not xml:
            continue
        domain = _domain(url)
        for loc in _parse_xml_urls(xml):
            low = loc.lower()
            if not _allowed(loc, domain):
                continue
            if ('sitemap' in low or low.endswith('.xml')) and loc not in seen:
                queue.append(loc)
                continue
            if (_productish_url(loc) or len(products) < 20) and loc not in products:
                products.append(loc)
                if len(products) >= limit:
                    break
    return products


def discover_urls(starts: list[str], max_pages: int, max_products: int) -> list[str]:
    starts = [_norm(url) for url in starts if _norm(url)]
    products = _discover_from_feeds(starts, max_products)
    queue: deque[str] = deque(starts + products)
    visited: set[str] = set()
    while queue and len(visited) < max_pages and len(products) < max_products:
        url = _norm(queue.popleft())
        if not url or url in visited:
            continue
        visited.add(url)
        page = _page(url)
        if page is None:
            continue
        if _productish_page(page) and url not in products:
            products.append(url)
        ordered = sorted(_links(page), key=lambda item: 0 if _productish_url(item) else 1)
        for link in ordered:
            if _productish_url(link) and link not in products:
                products.append(link)
                if len(products) >= max_products:
                    break
            if link not in visited and len(queue) + len(visited) < max_pages:
                queue.append(link)
        for n in range(2, 8):
            for suffix in [f'?page={n}', f'?pagina={n}', f'?p={n}', f'/page/{n}', f'/pagina/{n}']:
                paged = _norm(url.rstrip('/') + suffix if suffix.startswith('/') else url + ('&' if '?' in url else '?') + suffix[1:])
                if paged and paged not in visited and len(queue) + len(visited) < max_pages:
                    queue.append(paged)
    return (products or starts)[:max_products]


def _price(text: str) -> str:
    match = re.search(r'R\$\s*([0-9\.]+,[0-9]{2})', text)
    if match:
        return match.group(1)
    match = re.search(r'\b([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})\b', text)
    return match.group(1) if match else ''


def _stock(text: str) -> str:
    for pattern in [r'(?:estoque|saldo|quantidade|qtd)\s*[:\-]?\s*(\d{1,6})', r'(?:restam|resta|apenas)\s*(\d{1,6})']:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(1)
    key = normalize_key(text)
    if any(normalize_key(term) in key for term in OUT_STOCK):
        return '0'
    if any(normalize_key(term) in key for term in IN_STOCK):
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


def _images(node: Tag, base_url: str) -> str:
    found: list[str] = []
    for img in node.find_all('img'):
        src = img.get('src') or img.get('data-src') or img.get('data-lazy') or img.get('data-original') or img.get('data-zoom-image')
        if not src:
            continue
        url = urljoin(base_url, str(src))
        low = url.lower()
        if any(bad in low for bad in ['logo', 'sprite', 'placeholder', 'icon', 'whatsapp']):
            continue
        if url not in found:
            found.append(url)
    return '|'.join(found[:12])


def _title(node: Tag, fallback: str = '') -> str:
    for selector in ['h1', 'h2', 'h3', '[itemprop=name]', '.product-name', '.nome', '.name', '.titulo', '.title']:
        selected = node.select_one(selector)
        if selected:
            text = clean_cell(selected.get_text(' ', strip=True))
            if text:
                return text[:220]
    img = node.find('img')
    if img and img.get('alt'):
        return clean_cell(img.get('alt'))[:220]
    text = clean_cell(fallback or node.get_text(' ', strip=True))
    price = _price(text)
    if price:
        text = text.replace(price, '')
    return text[:220]


def _jsonld_rows(page: Page) -> list[dict[str, str]]:
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
                queue.extend(item); continue
            if not isinstance(item, dict):
                continue
            type_text = str(item.get('@type') or item.get('type') or '').lower()
            if 'product' in type_text or ('offers' in item and 'name' in item):
                offer = item.get('offers')
                if isinstance(offer, list):
                    offer = offer[0] if offer else {}
                offer = offer if isinstance(offer, dict) else {}
                brand = item.get('brand')
                brand_name = clean_cell(brand.get('name') if isinstance(brand, dict) else brand or '')
                image = item.get('image')
                image_value = '|'.join([clean_cell(x) for x in image]) if isinstance(image, list) else clean_cell(image or '')
                rows.append({'url': clean_cell(item.get('url') or page.url), 'codigo': clean_cell(item.get('sku') or item.get('mpn') or ''), 'gtin': clean_gtin(item.get('gtin') or item.get('gtin13') or item.get('gtin14') or ''), 'descricao': clean_cell(item.get('name') or ''), 'preco': clean_cell(offer.get('price') or ''), 'estoque': _stock(clean_cell(offer.get('availability') or '')), 'imagem': image_value, 'marca': brand_name, 'categoria': clean_cell(item.get('category') or '')})
            for value in item.values():
                if isinstance(value, (dict, list)):
                    queue.append(value)
    return rows


def _card_nodes(page: Page) -> list[Tag]:
    candidates: list[Tag] = []
    for node in page.soup.find_all(['article', 'li', 'div', 'tr']):
        text = clean_cell(node.get_text(' ', strip=True))
        if len(text) < 20:
            continue
        score = 0
        if node.find('a', href=True):
            score += 20
        if node.find('img'):
            score += 20
        if _price(text):
            score += 35
        if any(term in normalize_key(text) for term in ['produto', 'comprar', 'preco', 'preço', 'sku', 'codigo']):
            score += 25
        if score >= 40:
            candidates.append(node)
    signatures = Counter(f"{n.name}:{'.'.join(sorted(str(c) for c in n.get('class', [])))}" for n in candidates)
    repeated = {sig for sig, count in signatures.items() if count >= 2}
    output = [n for n in candidates if not repeated or f"{n.name}:{'.'.join(sorted(str(c) for c in n.get('class', [])))}" in repeated]
    return output[:250]


def _node_row(node: Tag, page: Page) -> dict[str, str]:
    text = clean_cell(node.get_text(' ', strip=True))
    link = node.find('a', href=True)
    url = _norm(urljoin(page.url, str(link.get('href') or ''))) if link else page.url
    return {'url': url or page.url, 'codigo': _code(text), 'gtin': _gtin(text), 'descricao': _title(node, text), 'preco': _price(text), 'estoque': _stock(text), 'imagem': _images(node, page.url), 'marca': '', 'categoria': ''}


def _single_row(page: Page) -> dict[str, str]:
    meta_title = page.soup.find('meta', property='og:title')
    title = clean_cell(meta_title.get('content')) if meta_title and meta_title.get('content') else _title(page.soup, page.text)
    meta_price = page.soup.find('meta', property='product:price:amount')
    price = clean_cell(meta_price.get('content')) if meta_price and meta_price.get('content') else _price(page.text)
    return {'url': page.url, 'codigo': _code(page.text), 'gtin': _gtin(page.text), 'descricao': title, 'preco': price, 'estoque': _stock(page.text), 'imagem': _images(page.soup, page.url), 'marca': '', 'categoria': ''}


def _generic_rows(page: Page) -> list[dict[str, str]]:
    rows = _jsonld_rows(page)
    rows.extend(_node_row(node, page) for node in _card_nodes(page))
    if _productish_page(page) or not rows:
        rows.append(_single_row(page))
    unique: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        key = normalize_key((row.get('url') or '') + '|' + (row.get('descricao') or '') + '|' + (row.get('codigo') or ''))
        if key and key not in seen and any(str(v).strip() for k, v in row.items() if k != 'url'):
            seen.add(key)
            unique.append(row)
    return unique


def _map(row: dict[str, str], contract: list[RequestedField]) -> dict[str, str]:
    out: dict[str, str] = {}
    for field in contract:
        if field.kind == 'url': out[field.original] = row.get('url', '')
        elif field.kind in {'codigo', 'id_produto'}: out[field.original] = row.get('codigo', '')
        elif field.kind == 'gtin': out[field.original] = row.get('gtin', '')
        elif field.kind in {'descricao', 'nome_apoio'}: out[field.original] = row.get('descricao', '')
        elif field.kind in {'preco_unitario', 'preco_custo'}: out[field.original] = row.get('preco', '')
        elif field.kind == 'estoque': out[field.original] = row.get('estoque', '')
        elif field.kind == 'imagem': out[field.original] = row.get('imagem', '')
        elif field.kind == 'marca': out[field.original] = row.get('marca', '')
        elif field.kind == 'categoria': out[field.original] = row.get('categoria', '')
        else: out[field.original] = ''
    return out


def _ensure(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for column in columns:
        if column not in out.columns:
            out[column] = ''
    return out.loc[:, columns].fillna('')


def run_power_scraper(raw_urls: str, requested_columns: Iterable[str] | None = None, operation: str = 'cadastro', all_products: bool = True, max_pages: int = 250, max_products: int = 1000, keep_only_requested_columns: bool = True) -> pd.DataFrame:
    starts = split_urls(raw_urls)
    contract = build_contract(requested_columns or [])
    if not starts:
        return pd.DataFrame(columns=[f.original for f in contract])
    urls = discover_urls(starts, max_pages=max_pages, max_products=max_products) if all_products else starts
    rows: list[dict[str, str]] = []
    for url in urls[:max_products]:
        page = _page(url)
        if page is None:
            continue
        for generic in _generic_rows(page):
            if contract:
                mapped = _map(generic, contract)
                if any(not str(mapped.get(f.original, '')).strip() for f in contract):
                    mapped = enrich_row_with_ai(current_row=mapped, contract=contract, page_url=generic.get('url') or page.url, page_text=page.text, operation=operation)
                rows.append(mapped)
            else:
                rows.append({'URL': generic.get('url', ''), 'Código': generic.get('codigo', ''), 'SKU': generic.get('codigo', ''), 'GTIN': generic.get('gtin', ''), 'Descrição': generic.get('descricao', ''), 'Nome': generic.get('descricao', ''), 'Preço': generic.get('preco', ''), 'Preço unitário (OBRIGATÓRIO)': generic.get('preco', ''), 'Estoque': generic.get('estoque', ''), 'Balanço (OBRIGATÓRIO)': generic.get('estoque', ''), 'URL Imagens': generic.get('imagem', ''), 'Imagens': generic.get('imagem', ''), 'Marca': generic.get('marca', ''), 'Categoria': generic.get('categoria', '')})
            if len(rows) >= max_products:
                break
        if len(rows) >= max_products:
            break
    df = pd.DataFrame(rows).fillna('')
    if contract and keep_only_requested_columns:
        return _ensure(df, [f.original for f in contract])
    return df.fillna('')
