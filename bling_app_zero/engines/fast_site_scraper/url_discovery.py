from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

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
PRODUCT_PATH_HINTS = ['/produto/', '/product/', '/p/', '/item/', 'produto-', 'product-']
PRODUCT_QUERY_HINTS = {'sku', 'cod', 'codigo', 'ref', 'idproduto', 'product_id'}
BLOCKED_TERMS = ['facebook', 'instagram', 'youtube', 'whatsapp', 'mailto:', 'tel:', '/login', '/conta', '/checkout', '/cart', '/carrinho', '/blog', '/politica', '/termos']
HTML_DISCOVERY_PAGE_CAP = 350
HTML_DISCOVERY_BATCH = 36
FEED_BATCH = 36
SMART_URL_TARGET = 220
FULL_SCAN_URL_TARGET = 2500
MIN_HTML_PRODUCTS_TO_SKIP_FEED = 60
PUBLIC_HTML_DISCOVERY_ONLY = True


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
    parsed = urlparse(str(url or ''))
    low_path = (parsed.path or '').lower()
    low_url = str(url or '').lower()

    if any(hint in low_path for hint in PRODUCT_PATH_HINTS):
        return True

    query_keys = {key.lower() for key in parse_qs(parsed.query).keys()}
    if query_keys & PRODUCT_QUERY_HINTS:
        return True

    if re.search(r'/(produto|product)s?/[a-z0-9][a-z0-9._-]{2,}', low_path):
        return True
    if re.search(r'/(p|item)/[a-z0-9][a-z0-9._-]{2,}', low_path):
        return True

    return any(hint in low_url for hint in ['produto-', 'product-'])


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
    robots = fetch_live(f'{root}/robots.txt', timeout=5)
    for sitemap in robots_sitemaps(robots):
        if sitemap not in candidates:
            candidates.append(sitemap)
    return list(dict.fromkeys(candidates))


def discover_from_feeds(starts: list[str], max_products: int) -> list[str]:
    """Descobre URLs por feeds apenas para complemento controlado.

    Esta função não deve criar linhas na busca ao vivo. Produto vindo somente
    de feed/cache/API/teste precisa ser descartado se não existir na lista
    pública viva encontrada por HTML.
    """
    queue: list[str] = []
    for start in starts:
        queue.extend(feed_candidates(start))
    queue = list(dict.fromkeys(queue))

    products: list[str] = []
    seen_feeds: set[str] = set()

    while queue and len(products) < max_products:
        batch = [url for url in queue[:FEED_BATCH] if url not in seen_feeds]
        queue = queue[FEED_BATCH:]
        if not batch:
            continue
        for url in batch:
            seen_feeds.add(url)
        fetched = fetch_many_live(batch, timeout=5, workers=18)
        for raw in fetched.values():
            if not raw:
                continue
            for loc in xml_urls(raw):
                if not any(same_domain(loc, start) for start in starts):
                    continue
                low = loc.lower()
                if ('sitemap' in low or low.endswith('.xml')) and loc not in seen_feeds and loc not in queue:
                    queue.append(loc)
                    continue
                if productish_url(loc) and loc not in products:
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
    page_limit = min(max_pages, HTML_DISCOVERY_PAGE_CAP)

    while queue and len(visited) < page_limit and len(products) < max_products:
        batch = [url for url in queue[:HTML_DISCOVERY_BATCH] if url not in visited]
        queue = queue[HTML_DISCOVERY_BATCH:]
        if not batch:
            continue
        for url in batch:
            visited.add(url)
        fetched = fetch_many_live(batch, timeout=5, workers=18)
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
                if link not in visited and link not in queue and len(visited) + len(queue) < page_limit:
                    queue.append(link)
    return products[:max_products]


def _smart_target(max_products: int) -> int:
    """Define o alvo da descoberta sem travar a busca ampla."""
    try:
        requested = int(max_products or 0)
    except Exception:
        requested = SMART_URL_TARGET
    if requested <= 0:
        return SMART_URL_TARGET
    if requested <= SMART_URL_TARGET:
        return requested
    return min(requested, FULL_SCAN_URL_TARGET)


def discover_product_urls(raw_urls: str, max_pages: int, max_products: int) -> list[str]:
    starts = [norm_url(url) for url in split_urls(raw_urls) if norm_url(url)]
    if not starts:
        return []

    smart_target = _smart_target(max_products)
    direct_products = [url for url in starts if productish_url(url)]
    only_direct_products = bool(direct_products) and len(direct_products) == len(starts)
    if only_direct_products:
        return direct_products[:max_products]

    urls: list[str] = []
    for url in direct_products:
        if url not in urls:
            urls.append(url)

    # BLINGFIX ORIGEM VIVA:
    # A descoberta de produtos na busca ao vivo usa apenas HTML público.
    # Feeds/sitemaps/API/cache/testes podem complementar depois, mas nunca
    # criar produto novo fora da lista viva encontrada na URL informada.
    html_urls = discover_from_html(starts, max_pages=max_pages, max_products=smart_target)
    for url in html_urls:
        if url not in urls:
            urls.append(url)
            if len(urls) >= smart_target:
                return urls[:smart_target]

    return urls[:smart_target]
