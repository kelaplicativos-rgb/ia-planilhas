from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.engines.fast_site_scraper.catalog_api_discovery import discover_from_public_catalog_apis
from bling_app_zero.engines.fast_site_scraper.http_client import fetch_live, fetch_many_live
from bling_app_zero.engines.fast_site_scraper.wbuy_parser import html_has_wbuy_product, wbuy_product_links

COMMON_FEEDS = [
    'robots.txt',
    'sitemap.xml',
    'sitemap_index.xml',
    'sitemap-products.xml',
    'sitemap_products_1.xml',
    'product-sitemap.xml',
    'products-sitemap.xml',
    'produtos.xml',
    'produtos-sitemap.xml',
    'sitemap-produtos.xml',
    'products.xml',
    'google.xml',
    'merchant.xml',
    'facebook.xml',
    'catalog.xml',
    'catalogo.xml',
    'feed.xml',
]
PRODUCT_PATH_HINTS = ['/produto/', '/produtos/', '/product/', '/products/', '/p/', '/item/', 'produto-', 'product-']
PRODUCT_QUERY_HINTS = {'sku', 'cod', 'codigo', 'ref', 'idproduto', 'product_id', 'variant'}
ROOT_PRODUCT_BLOCKLIST = {
    'busca', 'ofertas', 'login', 'carrinho', 'checkout', 'conta', 'blog', 'marca',
    'm', 'politica', 'termos', 'atendimento', 'dropshipping', 'revenda', 'smartwatch',
    'acessorios', 'mais-produtos', 'celulares-smartphone',
}
BLOCKED_TERMS = [
    'facebook', 'instagram', 'youtube', 'whatsapp', 'mailto:', 'tel:', '/login', '/conta',
    '/checkout', '/cart', '/carrinho', '/blog', '/politica', '/termos', '/action.php',
    '/global.php', '/loadcomponents', '/anti-bot-check', '/recaptcha/', '/service_worker',
    '/webworker',
]
NON_CAPTURE_HOSTS = {
    'cdn.sistemawbuy.com.br',
    'fonts.googleapis.com',
    'fonts.gstatic.com',
    'www.google-analytics.com',
    'google-analytics.com',
    'www.googletagmanager.com',
    'googletagmanager.com',
    'www.google.com',
    'google.com',
    'www.gstatic.com',
    'gstatic.com',
    'www.mercadopago.com',
    'mercadopago.com',
}
NON_CAPTURE_ASSET_RE = re.compile(r'\.(jpg|jpeg|png|webp|gif|svg|css|js|pdf|zip|rar|woff2?|ttf|eot|map)(\?|$)', re.I)
RAW_URL_RE = re.compile(r'https?://[^\s\'"<>\\]+', re.I)
HTML_DISCOVERY_PAGE_CAP = 350
HTML_DISCOVERY_BATCH = 36
FEED_BATCH = 36
SMART_URL_TARGET = 220
FULL_SCAN_URL_TARGET = 2500
RESPONSIBLE_FILE = 'bling_app_zero/engines/fast_site_scraper/url_discovery.py'


def _clean_raw_url(value: str) -> str:
    return str(value or '').strip().strip('"\'`').rstrip(');,')


def _raw_url_candidates(raw: str) -> list[str]:
    text = str(raw or '')
    candidates: list[str] = []
    for item in re.split(r'[\n,;]+', text):
        clean = _clean_raw_url(item)
        if clean.startswith(('http://', 'https://')):
            candidates.append(clean)
    candidates.extend(_clean_raw_url(match) for match in RAW_URL_RE.findall(text))
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def _is_non_capture_url(url: str) -> bool:
    parsed = urlparse(str(url or ''))
    host = parsed.netloc.lower().replace('www.', '')
    low = str(url or '').lower()
    if host in {item.replace('www.', '') for item in NON_CAPTURE_HOSTS}:
        return True
    if any(term in low for term in BLOCKED_TERMS):
        return True
    if NON_CAPTURE_ASSET_RE.search(low):
        return True
    return False


def _audit_raw_url_filter(raw_urls: str, starts: list[str]) -> None:
    raw_candidates = [norm_url(url) for url in _raw_url_candidates(raw_urls) if norm_url(url)]
    if not raw_candidates:
        return
    ignored = [url for url in raw_candidates if _is_non_capture_url(url)]
    wbuy_assets = [url for url in raw_candidates if 'cdn.sistemawbuy.com.br' in url.lower() or 'produtos_categorias.css' in url.lower()]
    if ignored:
        add_audit_event(
            'site_scraper_non_product_urls_ignored',
            area='SITE',
            step='entrada',
            status='INFO',
            details={
                'raw_urls_found': len(raw_candidates),
                'ignored': len(ignored),
                'accepted': len(starts),
                'examples': ignored[:8],
                'responsible_file': RESPONSIBLE_FILE,
            },
        )
    if wbuy_assets:
        add_audit_event(
            'site_scraper_wbuy_css_detected',
            area='SITE',
            step='entrada',
            status='INFO',
            details={
                'assets': len(wbuy_assets),
                'accepted_starts': len(starts),
                'wbuy_platform_confirmed_by_cdn': True,
                'responsible_file': RESPONSIBLE_FILE,
            },
        )


def split_urls(raw: str) -> list[str]:
    urls: list[str] = []
    for candidate in _raw_url_candidates(raw):
        clean = norm_url(candidate)
        if not clean or _is_non_capture_url(clean):
            continue
        if clean not in urls:
            urls.append(clean)
    return urls


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


def _root_slug_productish(url: str) -> bool:
    parsed = urlparse(str(url or ''))
    path = (parsed.path or '').strip('/')
    if not path or '/' in path or len(path) < 8 or len(path) > 180:
        return False
    slug = path.lower()
    if slug in ROOT_PRODUCT_BLOCKLIST or slug.startswith(('m/', 'marca/')):
        return False
    if re.search(r'\.(html?|php|xml|json|jpg|jpeg|png|webp|gif|svg|css|js)$', slug):
        return False
    return slug.count('-') >= 2 and bool(re.search(r'[a-z0-9]-[a-z0-9]', slug))


def productish_url(url: str) -> bool:
    parsed = urlparse(str(url or ''))
    low_path = (parsed.path or '').lower()
    low_url = str(url or '').lower()

    if any(hint in low_path for hint in PRODUCT_PATH_HINTS):
        return True

    query_keys = {key.lower() for key in parse_qs(parsed.query).keys()}
    if query_keys & PRODUCT_QUERY_HINTS:
        return True

    if re.search(r'/(produto|produtos|product|products)s?/[a-z0-9][a-z0-9._-]{2,}', low_path):
        return True
    if re.search(r'/(p|item)/[a-z0-9][a-z0-9._-]{2,}', low_path):
        return True
    if re.search(r'/[a-z0-9][a-z0-9._-]{2,}/p/?$', low_path):
        return True
    if _root_slug_productish(url):
        return True

    return any(hint in low_url for hint in ['produto-', 'product-'])


def allowed_url(url: str, base: str) -> bool:
    low = url.lower()
    return (
        url.startswith(('http://', 'https://'))
        and same_domain(url, base)
        and not any(term in low for term in BLOCKED_TERMS)
        and not NON_CAPTURE_ASSET_RE.search(low)
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
    wbuy_links = wbuy_product_links(url, html)
    wbuy_set = set(wbuy_links)
    for href in wbuy_links:
        if href not in links:
            links.append(href)
    for node in soup.find_all('a', href=True):
        href = norm_url(urljoin(url, str(node.get('href') or '')))
        if href and allowed_url(href, url) and href not in links:
            links.append(href)
    return sorted(links, key=lambda item: 0 if item in wbuy_set or productish_url(item) else 1)


def _add_product_url(products: list[str], url: str, max_products: int) -> None:
    if url and url not in products and len(products) < max_products:
        products.append(url)


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
            is_wbuy_product_page = html_has_wbuy_product(html)
            if productish_url(url) or is_wbuy_product_page:
                _add_product_url(products, url, max_products)
            if is_wbuy_product_page:
                continue
            page_wbuy_links = set(wbuy_product_links(url, html))
            for link in _links_from_html(url, html):
                if (productish_url(link) or link in page_wbuy_links) and link not in products:
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


def _extend_unique(target: list[str], items: list[str], limit: int) -> list[str]:
    for url in items:
        if url and url not in target:
            target.append(url)
            if len(target) >= limit:
                break
    return target


def _remaining_target(urls: list[str], smart_target: int) -> int:
    return max(0, int(smart_target) - len(urls))


def discover_product_urls(raw_urls: str, max_pages: int, max_products: int) -> list[str]:
    starts = [norm_url(url) for url in split_urls(raw_urls) if norm_url(url)]
    _audit_raw_url_filter(raw_urls, starts)
    if not starts:
        return []

    smart_target = _smart_target(max_products)
    direct_products = [url for url in starts if productish_url(url)]
    only_direct_products = bool(direct_products) and len(direct_products) == len(starts)
    if only_direct_products:
        return direct_products[:max_products]

    urls: list[str] = []
    _extend_unique(urls, direct_products, smart_target)

    api_urls = discover_from_public_catalog_apis(starts, max_products=smart_target)
    _extend_unique(urls, api_urls, smart_target)
    if len(urls) >= smart_target:
        return urls[:smart_target]

    # Para varredura completa, não pare só porque o HTML achou alguns produtos.
    # Feeds/sitemaps costumam ter o catálogo inteiro e devem sempre complementar
    # enquanto ainda houver espaço até max_products.
    feed_limit = _remaining_target(urls, smart_target)
    if feed_limit:
        feed_urls = discover_from_feeds(starts, max_products=feed_limit)
        _extend_unique(urls, feed_urls, smart_target)
    if len(urls) >= smart_target:
        return urls[:smart_target]

    html_limit = _remaining_target(urls, smart_target)
    if html_limit:
        html_urls = discover_from_html(starts, max_pages=max_pages, max_products=html_limit)
        _extend_unique(urls, html_urls, smart_target)

    return urls[:smart_target]
