from __future__ import annotations

import json
import re
from urllib.parse import urlencode, urljoin, urlparse, urlunparse

from bling_app_zero.engines.fast_site_scraper.http_client import fetch_many_live

API_BATCH = 28
JSON_NODE_LIMIT = 6500
PRODUCT_PATH_HINTS = (
    '/produto/',
    '/produtos/',
    '/product/',
    '/products/',
    '/p/',
    '/item/',
    'produto-',
    'product-',
)
URL_KEYS = {
    'url',
    'link',
    'href',
    'permalink',
    'canonicalurl',
    'canonical_url',
    'producturl',
    'product_url',
    'produtourl',
    'produto_url',
    'urlproduto',
    'url_produto',
}
SLUG_KEYS = {'handle', 'slug', 'urlkey', 'url_key', 'linktext', 'urlslug', 'url_slug', 'permalinkslug', 'permalink_slug'}
BLOCKED_TERMS = (
    'facebook',
    'instagram',
    'youtube',
    'whatsapp',
    'mailto:',
    'tel:',
    '/login',
    '/conta',
    '/checkout',
    '/cart',
    '/carrinho',
    '/blog',
)
ROOT_PRODUCT_BLOCKLIST = {
    'busca', 'ofertas', 'login', 'carrinho', 'checkout', 'conta', 'blog', 'marca',
    'm', 'politica', 'termos', 'atendimento', 'dropshipping', 'revenda', 'smartwatch',
    'acessorios', 'mais-produtos', 'celulares-smartphone',
}
WBUY_SEARCH_TERMS = (
    'smartwatch', 'peje', 'microwear', 'fone', 'caixa', 'camera', 'xiaomi', 'iphone', 'produto'
)


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
    if re.search(r'/(produto|produtos|product|products)s?/[a-z0-9][a-z0-9._-]{2,}', low_path):
        return True
    if re.search(r'/(p|item)/[a-z0-9][a-z0-9._-]{2,}', low_path):
        return True
    if re.search(r'/[a-z0-9][a-z0-9._-]{2,}/p/?$', low_path):
        return True
    if _root_slug_productish(url):
        return True
    return any(hint in low_url for hint in ('produto-', 'product-'))


def allowed_url(url: str, base: str) -> bool:
    low = str(url or '').lower()
    return (
        url.startswith(('http://', 'https://'))
        and same_domain(url, base)
        and not any(term in low for term in BLOCKED_TERMS)
        and not re.search(r'\.(jpg|jpeg|png|webp|gif|svg|css|js|pdf|zip|rar)(\?|$)', low)
    )


def _append_unique(target: list[str], url: str, base: str, max_items: int) -> None:
    clean = norm_url(url)
    if clean and allowed_url(clean, base) and productish_url(clean) and clean not in target and len(target) < max_items:
        target.append(clean)


def _json_text(raw: str) -> str:
    text = str(raw or '').strip()
    if not text:
        return ''
    if text[0] in '[{':
        return text
    match = re.search(r'(\{.*\}|\[.*\])', text, flags=re.S)
    return match.group(1).strip() if match else ''


def _load_json(raw: str):
    text = _json_text(raw)
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def _slug_to_urls(value: str, base: str, key: str) -> list[str]:
    slug = str(value or '').strip().strip('/')
    if not slug or len(slug) < 3 or len(slug) > 180 or re.search(r'\s', slug):
        return []
    low = slug.lower()
    if low.startswith(('http:', 'https:', '#')) or any(mark in low for mark in ('{', '}', '<', '>')):
        return []

    root = root_url(base).rstrip('/')
    key_low = key.lower()
    if key_low == 'handle':
        return [f'{root}/products/{slug}']
    if key_low in {'linktext', 'urlkey', 'url_key'}:
        return [f'{root}/{slug}/p', f'{root}/produto/{slug}', f'{root}/{slug}']
    return [f'{root}/produto/{slug}', f'{root}/products/{slug}', f'{root}/{slug}/p', f'{root}/{slug}']


def _string_to_urls(value: str, base: str, key: str = '') -> list[str]:
    text = str(value or '').strip()
    if not text:
        return []

    text = text.replace('\\/', '/').replace('&amp;', '&').strip('"\'')
    if text.startswith('//'):
        text = f'https:{text}'

    if text.startswith(('http://', 'https://')):
        return [text]
    if text.startswith('/'):
        return [urljoin(root_url(base), text)]

    if key.lower() in SLUG_KEYS:
        return _slug_to_urls(text, base, key)
    return []


def _urls_from_json_obj(data, base: str, max_items: int) -> list[str]:
    found: list[str] = []
    visited = 0

    def walk(node, parent_key: str = '') -> None:
        nonlocal visited
        if visited >= JSON_NODE_LIMIT or len(found) >= max_items:
            return
        visited += 1

        if isinstance(node, dict):
            for key, value in node.items():
                key_norm = re.sub(r'[^a-z0-9]+', '', str(key).lower())
                if isinstance(value, str) and (key_norm in URL_KEYS or key_norm in SLUG_KEYS):
                    for candidate in _string_to_urls(value, base, key_norm):
                        _append_unique(found, candidate, base, max_items)
                walk(value, str(key))
            return

        if isinstance(node, list):
            for item in node:
                walk(item, parent_key)
            return

        if isinstance(node, str) and parent_key:
            key_norm = re.sub(r'[^a-z0-9]+', '', parent_key.lower())
            if key_norm in URL_KEYS or key_norm in SLUG_KEYS:
                for candidate in _string_to_urls(node, base, key_norm):
                    _append_unique(found, candidate, base, max_items)

    walk(data)
    return found[:max_items]


def urls_from_json_text(raw: str, base: str, max_items: int) -> list[str]:
    data = _load_json(raw)
    if data is None:
        return []
    return _urls_from_json_obj(data, base, max_items)


def urls_from_embedded_text(raw: str, base: str, max_items: int) -> list[str]:
    found: list[str] = []
    text = str(raw or '').replace('\\/', '/').replace('&amp;', '&')
    for match in re.findall(r'https?://[^"\'<>\s)]+', text):
        _append_unique(found, match, base, max_items)
        if len(found) >= max_items:
            return found
    for match in re.findall(r'["\'](/[^"\']+)["\']', text, flags=re.I):
        _append_unique(found, urljoin(root_url(base), match), base, max_items)
        if len(found) >= max_items:
            return found
    return found[:max_items]


def _api_candidates_for_root(root: str) -> list[str]:
    root = root.rstrip('/')
    candidates: list[str] = []
    for page in range(1, 5):
        candidates.append(f'{root}/products.json?{urlencode({"limit": 250, "page": page})}')
        candidates.append(f'{root}/collections/all/products.json?{urlencode({"limit": 250, "page": page})}')
        candidates.append(f'{root}/wp-json/wc/store/v1/products?{urlencode({"per_page": 100, "page": page})}')
        candidates.append(f'{root}/wp-json/wp/v2/product?{urlencode({"per_page": 100, "page": page})}')
        start = (page - 1) * 100
        candidates.append(f'{root}/api/catalog_system/pub/products/search?{urlencode({"_from": start, "_to": start + 99})}')
    for term in WBUY_SEARCH_TERMS:
        for query_key in ('q', 'term', 'query', 'keyword'):
            candidates.append(f'{root}/produtos_autocomplete.php?{urlencode({query_key: term})}')
        candidates.append(f'{root}/busca/?{urlencode({"q": term})}')
    candidates.append(f'{root}/api/catalog_system/pub/category/tree/10')
    candidates.append(f'{root}/catalog/products.json')
    candidates.append(f'{root}/catalogo.json')
    return list(dict.fromkeys(candidates))


def discover_from_public_catalog_apis(starts: list[str], max_products: int) -> list[str]:
    """Descobre URLs por APIs/catálogos públicos e cai para vazio se não existir.

    Cobre Shopify, WooCommerce/Store API, WordPress Product API, VTEX, wBuy
    busca/autocomplete e catálogos JSON simples. A função só devolve URLs
    públicas; a extração do produto segue pelo scraper central.
    """
    products: list[str] = []
    candidates: list[str] = []
    for start in starts:
        candidates.extend(_api_candidates_for_root(root_url(start)))
    candidates = list(dict.fromkeys(candidates))

    for offset in range(0, len(candidates), API_BATCH):
        if len(products) >= max_products:
            break
        batch = candidates[offset:offset + API_BATCH]
        fetched = fetch_many_live(batch, timeout=8, workers=14)
        for url, raw in fetched.items():
            if not raw:
                continue
            base = root_url(url)
            for product_url in urls_from_json_text(raw, base, max_products - len(products)):
                if product_url not in products:
                    products.append(product_url)
                    if len(products) >= max_products:
                        break
            if len(products) >= max_products:
                break
            for product_url in urls_from_embedded_text(raw, base, max_products - len(products)):
                if product_url not in products:
                    products.append(product_url)
                    if len(products) >= max_products:
                        break
            if len(products) >= max_products:
                break
    return products[:max_products]


__all__ = [
    'discover_from_public_catalog_apis',
    'urls_from_embedded_text',
    'urls_from_json_text',
]
