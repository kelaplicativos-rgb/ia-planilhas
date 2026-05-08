from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from bling_app_zero.engines.fast_site_scraper.http_client import fetch_live, fetch_many_live

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


def split_urls(raw: str) -> list[str]:
    return [item.strip() for item in re.split(r'[\n,;]+', str(raw or '')) if item.strip().startswith(('http://', 'https://'))]


def norm_url(url: str) -> str:
    parsed = urlparse(str(url or '').strip())
    if not parsed.scheme or not parsed.netloc:
        return ''
    clean = parsed._replace(fragment='', path=re.sub(r'/+', '/', parsed.path or '/'))
    return urlunparse(clean).rstrip('/')


def root_url(url: str) -> str:
    parsed = urlparse(url)
    return f'{parsed.scheme}://{parsed.netloc}'


def domain(url: str) -> str:
    return urlparse(url).netloc.lower().replace('www.', '')


def same_domain(url: str, base: str) -> bool:
    host = domain(url)
    root = domain(base)
    return host == root or host.endswith('.' + root)


def productish_url(url: str) -> bool:
    low = url.lower()
    return any(hint in low for hint in PRODUCT_HINTS)


def allowed_url(url: str, base: str) -> bool:
    low = url.lower()
    return (
        url.startswith(('http://', 'https://'))
        and same_domain(url, base)
        and not any(term in low for term in BLOCKED_TERMS)
        and not re.search(r'\.(jpg|jpeg|png|webp|gif|svg|css|js|pdf|zip|rar)(\?|$)', low)
    )


def xml_urls(raw: str) -> list[str]:
    urls = re.findall(r'<loc>\s*([^<]+?)\s*</loc>', raw or '', flags=re.I)
    urls += re.findall(r'<g:link>\s*([^<]+?)\s*</g:link>', raw or '', flags=re.I)
    urls += re.findall(r'<link>\s*([^<]+?)\s*</link>', raw or '', flags=re.I)
    return [norm_url(url) for url in urls if norm_url(url)]


def robots_sitemaps(raw: str) -> list[str]:
    return [norm_url(match) for match in re.findall(r'(?im)^\s*Sitemap:\s*(\S+)\s*$', raw or '') if norm_url(match)]


def feed_candidates(start: str) -> list[str]:
    root = root_url(start)
    candidates = [f'{root}/{feed}' for feed in COMMON_FEEDS]
    robots = fetch_live(f'{root}/robots.txt', timeout=8)
    for sitemap in robots_sitemaps(robots):
        if sitemap not in candidates:
            candidates.append(sitemap)
    return list(dict.fromkeys(candidates))


def discover_from_feeds(starts: list[str], max_products: int) -> list[str]:
    queue: list[str] = []
    for start in starts:
        queue.extend(feed_candidates(start))
    queue = list(dict.fromkeys(queue))

    products: list[str] = []
    seen_feeds: set[str] = set()

    while queue and len(products) < max_products:
        batch = [url for url in queue[:32] if url not in seen_feeds]
        queue = queue[32:]
        if not batch:
            continue
        for url in batch:
            seen_feeds.add(url)
        fetched = fetch_many_live(batch, timeout=8, workers=16)
        for feed_url, raw in fetched.items():
            if not raw:
                continue
            for loc in xml_urls(raw):
                if not any(same_domain(loc, start) for start in starts):
                    continue
                low = loc.lower()
                if ('sitemap' in low or low.endswith('.xml')) and loc not in seen_feeds and loc not in queue:
                    queue.append(loc)
                    continue
                if loc not in products:
                    products.append(loc)
                    if len(products) >= max_products:
                        break
    return products[:max_products]


def _links_from_html(url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html or '', 'html.parser')
    links: list[str] = []
    for node in soup.find_all('a', href=True):
        href = norm_url(urljoin(url, str(node.get('href') or '')))
        if href and allowed_url(href, url) and href not in links:
            links.append(href)
    return sorted(links, key=lambda item: 0 if productish_url(item) else 1)


def discover_from_html(starts: list[str], max_pages: int, max_products: int) -> list[str]:
    queue = list(dict.fromkeys(starts))
    visited: set[str] = set()
    products: list[str] = []

    while queue and len(visited) < max_pages and len(products) < max_products:
        batch = [url for url in queue[:24] if url not in visited]
        queue = queue[24:]
        if not batch:
            continue
        for url in batch:
            visited.add(url)
        fetched = fetch_many_live(batch, timeout=8, workers=16)
        for url, html in fetched.items():
            if not html:
                continue
            if productish_url(url) and url not in products:
                products.append(url)
            for link in _links_from_html(url, html):
                if productish_url(link) and link not in products:
                    products.append(link)
                    if len(products) >= max_products:
                        break
                if link not in visited and link not in queue:
                    queue.append(link)
    return products[:max_products]


def discover_product_urls(raw_urls: str, max_pages: int, max_products: int) -> list[str]:
    starts = [norm_url(url) for url in split_urls(raw_urls) if norm_url(url)]
    if not starts:
        return []

    direct_products = [url for url in starts if productish_url(url)]
    category_starts = starts

    urls: list[str] = []
    for url in direct_products:
        if url not in urls:
            urls.append(url)

    for url in discover_from_feeds(category_starts, max_products=max_products):
        if url not in urls:
            urls.append(url)
            if len(urls) >= max_products:
                return urls

    for url in discover_from_html(category_starts, max_pages=max_pages, max_products=max_products):
        if url not in urls:
            urls.append(url)
            if len(urls) >= max_products:
                return urls

    return (urls or starts)[:max_products]
