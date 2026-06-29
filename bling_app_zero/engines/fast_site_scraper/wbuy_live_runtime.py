from __future__ import annotations

import html as html_lib
import json
import re
import time
from urllib.parse import urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.text import clean_cell, normalize_key
from bling_app_zero.engines.fast_site_scraper.http_client import fetch_live
from bling_app_zero.engines.fast_site_scraper.models import FastProductData

RESPONSIBLE_FILE = 'bling_app_zero/engines/fast_site_scraper/wbuy_live_runtime.py'
PAGE_CAP = 90
TARGET_CAP = 220


def _norm(url: object) -> str:
    parsed = urlparse(str(url or '').strip())
    if not parsed.scheme or not parsed.netloc:
        return ''
    parsed = parsed._replace(fragment='', path=re.sub(r'/+', '/', parsed.path or '/'))
    return urlunparse(parsed).rstrip('/')


def _root(url: str) -> str:
    parsed = urlparse(str(url or '').strip())
    return f'{parsed.scheme}://{parsed.netloc}' if parsed.scheme and parsed.netloc else ''


def _same(url: str, base: str) -> bool:
    host = urlparse(url).netloc.lower().replace('www.', '')
    root = urlparse(base).netloc.lower().replace('www.', '')
    return bool(host and root and (host == root or host.endswith('.' + root)))


def _add(items: list[str], url: object, limit: int = 0) -> None:
    value = _norm(url)
    if value and value not in items and (not limit or len(items) < limit):
        items.append(value)


def _money(value: object) -> str:
    if isinstance(value, (int, float)):
        return f'{float(value):.2f}'.replace('.', ',')
    text = clean_cell(value)
    found = re.search(r'([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+(?:[\.,][0-9]{2})?)', text)
    return found.group(1) if found else ''


def _pid(code: str) -> str:
    first = clean_cell(code).split('.', 1)[0]
    return first if first.isdigit() else ''


def _brand(name: str) -> str:
    key = normalize_key(name)
    for brand in ('Xiaomi', 'Apple', 'iPhone', 'Realme', 'Samsung', 'Motorola', 'Howear', 'Microwear', 'Haylou', 'Amazfit', 'Peje'):
        if normalize_key(brand) in key:
            return 'Apple' if brand.lower() == 'iphone' else brand
    return ''


def _merge(primary: list[FastProductData], extra: list[FastProductData], limit: int) -> list[FastProductData]:
    out: list[FastProductData] = []
    seen: set[str] = set()
    for product in [*primary, *extra]:
        key = (product.codigo or product.id_produto or product.url or product.descricao).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(product)
        if len(out) >= limit:
            break
    return out


def _card_index(base_url: str, html: str) -> dict[str, dict[str, str]]:
    soup = BeautifulSoup(html or '', 'html.parser')
    found: dict[str, dict[str, str]] = {}
    for card in soup.select('div.item[data-id][data-sku], .item[data-id][data-sku]'):
        sku = clean_cell(card.get('data-sku') or '')
        pid = clean_cell(card.get('data-id') or '')
        href = ''
        for node in card.select('a.b_acao[href], a[href]'):
            candidate = _norm(urljoin(base_url, str(node.get('href') or '')))
            if candidate and _same(candidate, base_url) and '#' not in candidate:
                href = candidate
                break
        images: list[str] = []
        for img in card.select('img[data-src], img[data-original], img[data-lazy], img[src]'):
            raw = img.get('data-src') or img.get('data-original') or img.get('data-lazy') or img.get('src') or ''
            img_url = clean_cell(urljoin(base_url, str(raw).split(',')[0].split()[0]))
            if img_url and '/produtos/' in img_url.lower() and img_url not in images:
                images.append(img_url)
        payload = {'url': href, 'imagem': '|'.join(images[:8])}
        for key in (sku, pid):
            if key:
                found[key] = payload
    return found


def _objects(text: str) -> list[dict]:
    decoded = html_lib.unescape(str(text or ''))
    out: list[dict] = []
    pattern = re.compile(r'\{[^{}]{0,1800}(?:"item_name"|"name")[^{}]{0,1800}(?:"item_id"|"id")[^{}]{0,1800}\}', re.I | re.S)
    for match in pattern.finditer(decoded):
        try:
            data = json.loads(re.sub(r',\s*([}\]])', r'\1', match.group(0)))
        except Exception:
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


def _datalayer(base_url: str, html: str, limit: int) -> list[FastProductData]:
    cards = _card_index(base_url, html)
    products: list[FastProductData] = []
    seen: set[str] = set()
    for item in _objects(html):
        name = clean_cell(item.get('item_name') or item.get('name') or '')[:240]
        code = clean_cell(item.get('item_id') or item.get('id') or '')
        if not name or not code or code.lower() in seen:
            continue
        seen.add(code.lower())
        extra = cards.get(code) or cards.get(_pid(code)) or {}
        products.append(FastProductData(
            url=clean_cell(extra.get('url') or ''),
            id_produto=_pid(code),
            codigo=code,
            descricao=name,
            preco=_money(item.get('price') or ''),
            estoque='10',
            imagem=clean_cell(extra.get('imagem') or ''),
            marca=clean_cell(item.get('item_brand') or item.get('brand') or '') or _brand(name),
            categoria=clean_cell(item.get('item_category') or item.get('category') or ''),
        ))
        if len(products) >= limit:
            break
    if products:
        add_audit_event('site_scraper_wbuy_datalayer_products', area='SITE', step='entrada', status='OK', details={'products': len(products), 'responsible_file': RESPONSIBLE_FILE})
    return products[:limit]


def _variants(url: str, pages: int = 12) -> list[str]:
    clean = _norm(url)
    parsed = urlparse(clean)
    root = _root(clean)
    path = parsed.path or '/'
    if not path.endswith('/'):
        path += '/'
    urls: list[str] = []
    _add(urls, clean)
    _add(urls, f'{root}{path}')
    for page in range(1, max(2, min(pages, 16)) + 1):
        _add(urls, f'{root}{path}?{urlencode({"page": page})}')
        if page > 1:
            _add(urls, f'{root}{path}?{urlencode({"order": "valor-asc", "page": page})}')
            _add(urls, f'{root}{path}?{urlencode({"pg": page})}')
            _add(urls, f'{root}{path}?{urlencode({"pagina": page})}')
    return urls


def _pagination(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html or '', 'html.parser')
    links: list[str] = []
    for node in soup.select('a[href*="page="], option[data-url*="page="], option[value*="page="], select option[value]'):
        raw = node.get('href') or node.get('data-url') or node.get('value') or ''
        url = _norm(urljoin(base_url, str(raw)))
        if url and _same(url, base_url) and re.search(r'[?&](page|pg|pagina)=', url):
            _add(links, url, 30)
    return links


def _target(max_products: int) -> int:
    try:
        requested = int(max_products or 0)
    except Exception:
        requested = 1200
    return max(24, min(requested if requested > 0 else 1200, TARGET_CAP))


def _polite(runner, raw_urls: str, max_products: int, progress_callback=None) -> list[FastProductData]:
    starts = [_norm(url) for url in runner.split_urls(raw_urls) if _norm(url)]
    if not starts:
        return []
    target = _target(max_products)
    queue: list[str] = []
    for start in starts:
        for url in _variants(start):
            _add(queue, url, PAGE_CAP)
    try:
        for url in runner._wbuy_candidate_pages(raw_urls, max_products)[:35]:
            _add(queue, url, PAGE_CAP)
    except Exception:
        pass
    if progress_callback:
        try:
            progress_callback({'stage': 'WBuy paginação', 'message': 'Lendo categorias, cards públicos e páginas WBuy.', 'progress': 0.885, 'candidate_pages': len(queue), 'responsible_file': RESPONSIBLE_FILE})
        except Exception:
            pass
    products: list[FastProductData] = []
    seen: set[str] = set()
    visited: set[str] = set()
    html_pages = 0
    pages_with_products = 0
    started = time.perf_counter()
    while queue and len(visited) < PAGE_CAP and len(products) < target:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        page_html = fetch_live(url, timeout=11)
        if not page_html:
            continue
        html_pages += 1
        count_before = len(products)
        for product in runner.wbuy_listing_products(url, page_html, limit=max(1, target - len(products))):
            key = (product.codigo or product.id_produto or product.url or product.descricao).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            products.append(product)
            if len(products) >= target:
                break
        if len(products) > count_before:
            pages_with_products += 1
        for link in _pagination(url, page_html):
            if link not in visited and link not in queue and len(queue) < PAGE_CAP:
                queue.append(link)
    add_audit_event('site_scraper_wbuy_polite_listing_finished', area='SITE', step='entrada', status='OK' if products else 'AVISO', details={'starts': len(starts), 'visited': len(visited), 'html_pages': html_pages, 'pages_with_products': pages_with_products, 'products': len(products), 'target': target, 'seconds': round(time.perf_counter() - started, 2), 'responsible_file': RESPONSIBLE_FILE})
    return products[:max_products]


def install() -> bool:
    from bling_app_zero.engines.fast_site_scraper import runner, wbuy_parser
    installed = False
    original_listing = getattr(wbuy_parser, 'wbuy_listing_products', None)
    if callable(original_listing) and not getattr(original_listing, '_wbuy_live_runtime_patch', False):
        def patched_listing(base_url: str, html: str, limit: int = 1200) -> list[FastProductData]:
            base_products = original_listing(base_url, html, limit)
            remaining = max(0, int(limit or 1200) - len(base_products))
            extra = _datalayer(base_url, html, remaining) if remaining else []
            return _merge(base_products, extra, int(limit or 1200))[:limit]
        patched_listing._wbuy_live_runtime_patch = True  # type: ignore[attr-defined]
        wbuy_parser.wbuy_listing_products = patched_listing
        runner.wbuy_listing_products = patched_listing
        installed = True
    original_fallback = getattr(runner, '_wbuy_listing_fallback_products', None)
    if callable(original_fallback) and not getattr(original_fallback, '_wbuy_live_runtime_patch', False):
        def patched_fallback(*, raw_urls: str, max_products: int, progress_callback=None, allow_catalog_fallback: bool = True) -> list[FastProductData]:
            products = _polite(runner, raw_urls, max_products, progress_callback=progress_callback)
            if products:
                return products[:max_products]
            return original_fallback(raw_urls=raw_urls, max_products=max_products, progress_callback=progress_callback, allow_catalog_fallback=allow_catalog_fallback)
        patched_fallback._wbuy_live_runtime_patch = True  # type: ignore[attr-defined]
        runner._wbuy_listing_fallback_products = patched_fallback
        installed = True
    add_audit_event('wbuy_live_runtime_installed', area='SITE', step='boot', status='OK' if installed else 'INFO', details={'installed': installed, 'datalayer_parser': True, 'pagination': True, 'responsible_file': RESPONSIBLE_FILE})
    return installed


__all__ = ['install']
