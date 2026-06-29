from __future__ import annotations

import re
import sys
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.text import clean_cell, normalize_key
from bling_app_zero.engines.fast_site_scraper.models import FastProductData

RESPONSIBLE_FILE = 'bling_app_zero/engines/fast_site_scraper/wbuy_cards_patch.py'

BLOCKED_URL_TERMS = (
    '/login', '/conta', '/checkout', '/cart', '/carrinho', '/blog', '/politica', '/termos',
    '/action.php', '/global.php', '/loadcomponents', '/anti-bot-check', '/recaptcha/',
    'facebook', 'instagram', 'youtube', 'whatsapp', 'mailto:', 'tel:', '#', 'javascript:',
    'google-analytics.com', 'googletagmanager.com', 'mercadolibre.com/jms/', 'fingerprint',
)
NOISE_TERMS = (
    'slide', 'slider', 'banner', 'carousel', 'owl-carousel', 'slick', 'swiper', 'menu',
    'header', 'footer', 'breadcrumb', 'social', 'newsletter', 'loading', 'logo',
)
BRAND_HINTS = (
    'Xiaomi', 'Samsung', 'Motorola', 'Apple', 'iPhone', 'Realme', 'Haylou', 'Amazfit',
    'Microwear', 'Peje', 'H\u2019maston', "H'maston", 'Kapbom', 'Lenovo', 'JBL', 'Awei',
)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or '', 'html.parser')


def _norm_url(url: str) -> str:
    parsed = urlparse(str(url or '').strip())
    if not parsed.scheme or not parsed.netloc:
        return ''
    clean = parsed._replace(fragment='', path=re.sub(r'/+', '/', parsed.path or '/'))
    return urlunparse(clean).rstrip('/')


def _same_domain(url: str, base_url: str) -> bool:
    host = urlparse(url).netloc.lower().replace('www.', '')
    root = urlparse(base_url).netloc.lower().replace('www.', '')
    return bool(host and root and (host == root or host.endswith('.' + root)))


def _allowed_url(url: str, base_url: str) -> bool:
    low = str(url or '').lower()
    if not url.startswith(('http://', 'https://')):
        return False
    if not _same_domain(url, base_url):
        return False
    if any(term in low for term in BLOCKED_URL_TERMS):
        return False
    if re.search(r'\.(jpg|jpeg|png|webp|gif|svg|css|js|pdf|zip|rar|woff2?|ttf|eot|map)(\?|$)', low):
        return False
    return True


def _append_unique(values: list[str], value: object, limit: int = 0) -> None:
    text = clean_cell(value)
    if text and text not in values and (not limit or len(values) < limit):
        values.append(text)


def _clean_price(value: object) -> str:
    text = clean_cell(value or '')
    if not text:
        return ''
    matches = re.findall(r'(?:R\$\s*)?([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+(?:[\.,][0-9]{2})?)', text)
    return matches[-1] if matches else ''


def _node_marker(node) -> str:
    parts: list[str] = []
    for key in ('id', 'class', 'role', 'aria-label'):
        raw = node.get(key) if hasattr(node, 'get') else ''
        if isinstance(raw, (list, tuple)):
            raw = ' '.join(str(item) for item in raw)
        parts.append(str(raw or ''))
    return normalize_key(' '.join(parts))


def _has_product_signature(node) -> bool:
    return bool(
        clean_cell(node.get('data-id') or '')
        or clean_cell(node.get('data-sku') or '')
        or node.select_one('h3.produto, .valor_final, [itemprop="name"], [itemprop="price"]')
    )


def _is_noise_node(node) -> bool:
    if _has_product_signature(node):
        return False
    current = node
    for _ in range(5):
        if current is None:
            break
        marker = _node_marker(current)
        if any(term in marker for term in NOISE_TERMS):
            return True
        current = getattr(current, 'parent', None)
    return False


def _card_nodes(soup: BeautifulSoup) -> list:
    selectors = (
        'div.item[data-id][data-sku]',
        '.produtos div.item[data-id][data-sku]',
        '.prod div.item[data-id][data-sku]',
        '.vitrine div.item[data-id][data-sku]',
        '.showcase div.item[data-id][data-sku]',
        '[itemtype*="schema.org/Product"]',
    )
    nodes: list = []
    for selector in selectors:
        for node in soup.select(selector):
            if node not in nodes and not _is_noise_node(node):
                nodes.append(node)
    return nodes


def _href_from_card(card, base_url: str) -> str:
    for selector in ('a.b_acao[href]', 'a[href*="produto"]', 'a[href*="product"]', 'a[href]'):
        for node in card.select(selector):
            href = str(node.get('href') or '').strip()
            url = _norm_url(urljoin(base_url, href))
            if url and _allowed_url(url, base_url):
                return url
    return ''


def _image_from_node(node, base_url: str) -> str:
    raw = (
        node.get('data-zoom-image')
        or node.get('data-src')
        or node.get('data-original')
        or node.get('data-lazy')
        or node.get('data-srcset')
        or node.get('srcset')
        or node.get('src')
        or ''
    )
    raw = str(raw).split(',')[0].split()[0].strip()
    url = clean_cell(urljoin(base_url, raw))
    low = url.lower()
    if not url:
        return ''
    if any(term in low for term in ['logo', 'sprite', 'placeholder', 'icon', 'blank.gif', '/slide/', '/banner/', 'story-queima']):
        return ''
    if 'cdn.sistemawbuy.com.br' in low and '/produtos/' not in low:
        return ''
    if re.search(r'\.(css|js|svg|woff2?|ttf|eot|map)(\?|$)', low):
        return ''
    return url


def _images_from_card(card, base_url: str, limit: int = 8) -> str:
    urls: list[str] = []
    for node in card.select('img[data-zoom-image], img[data-src], img[data-original], img[data-lazy], img[src], img[srcset], source[srcset]'):
        _append_unique(urls, _image_from_node(node, base_url), limit)
    return '|'.join(urls[:limit])


def _name_from_card(card) -> str:
    for selector in (
        'h3.produto', '.produto h3', '[itemprop="name"]', '.product-name', '.nome_produto',
        '.nome-produto', '.name', '.title', 'a[title]', 'h2', 'h3',
    ):
        node = card.select_one(selector)
        if not node:
            continue
        value = clean_cell(node.get('title') or node.get('alt') or node.get_text(' ', strip=True))[:240]
        if value and normalize_key(value) not in {'grupos', 'banner', 'slide', 'menu', 'logo', 'imagem', 'loading'}:
            return value
    image = card.select_one('img[alt]')
    value = clean_cell(image.get('alt') if image else '')[:240]
    if normalize_key(value) in {'grupos', 'banner', 'slide', 'menu', 'logo', 'imagem', 'loading'}:
        return ''
    return value


def _price_from_card(card) -> str:
    for selector in (
        '.valor_final span', '.valor_final', '[itemprop="price"]', 'meta[itemprop="price"]',
        '.price', '.preco', '.preço', '[class*="price"]', '[class*="preco"]', '[class*="valor"]',
    ):
        node = card.select_one(selector)
        if not node:
            continue
        value = _clean_price(node.get('content') or node.get_text(' ', strip=True))
        if value:
            return value
    return _clean_price(card.get_text(' ', strip=True))


def _old_price_from_card(card) -> str:
    text = card.get_text(' ', strip=True)
    matches = re.findall(r'(?:De|Antes|preço antigo|preco antigo)\s*R?\$?\s*([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})', text, flags=re.I)
    return matches[-1] if matches else ''


def _category(base_url: str, soup: BeautifulSoup) -> str:
    crumbs: list[str] = []
    for node in soup.select('.breadcrumb [itemprop="name"], .breadcrumb a, [aria-label*=breadcrumb] a, nav[aria-label*=breadcrumb] a'):
        text = clean_cell(node.get_text(' ', strip=True))
        key = normalize_key(text)
        if key and key not in {'home', 'inicio', 'pagina inicial'} and text not in crumbs:
            crumbs.append(text)
    if crumbs:
        return crumbs[-1]
    title = clean_cell(soup.title.get_text(' ', strip=True) if soup.title else '')
    title = re.sub(r'^comprar\s+', '', title, flags=re.I).strip()
    title = re.sub(r'\s+[-|].*$', '', title).strip()
    if title and 'atacadum' not in normalize_key(title):
        return title[:120]
    path = urlparse(base_url).path.strip('/')
    return clean_cell(path.replace('-', ' ').title())[:120] if path else ''


def _brand_from_name(name: str) -> str:
    name_key = normalize_key(name)
    for brand in BRAND_HINTS:
        if normalize_key(brand) in name_key:
            return 'Apple' if brand.lower() == 'iphone' else brand.replace('\u2019', "'")
    return ''


def _stock_from_card(card, price: str) -> str:
    text = normalize_key(card.get_text(' ', strip=True))
    if any(term in text for term in ('esgotado', 'indisponivel', 'fora de estoque')):
        return '0'
    if 'comprar' in text or price:
        return '10'
    return ''


def _product_from_card(base_url: str, card, category: str) -> FastProductData | None:
    url = _href_from_card(card, base_url)
    if not url:
        return None
    product_id = clean_cell(card.get('data-id') or card.get('data-product-id') or card.get('data-produtoid') or '')
    sku = clean_cell(card.get('data-sku') or card.get('data-codigo') or card.get('data-code') or '')
    name = _name_from_card(card)
    price = _price_from_card(card)
    images = _images_from_card(card, base_url)
    if not name or not (price or images or product_id or sku):
        return None
    old_price = _old_price_from_card(card)
    complement = f'Preço anterior: {old_price}' if old_price and old_price != price else ''
    return FastProductData(
        url=url,
        id_produto=product_id,
        codigo=sku or product_id,
        descricao=name,
        descricao_complementar=complement,
        preco=price,
        estoque=_stock_from_card(card, price),
        imagem=images,
        marca=_brand_from_name(name),
        categoria=category,
    )


def wbuy_product_links(base_url: str, html: str, limit: int = 1200) -> list[str]:
    soup = _soup(html)
    links: list[str] = []

    def add(href: object) -> None:
        url = _norm_url(urljoin(base_url, str(href or '').strip()))
        if url and _allowed_url(url, base_url) and url not in links and len(links) < limit:
            links.append(url)

    for card in _card_nodes(soup):
        href = _href_from_card(card, base_url)
        if href:
            add(href)
    for node in soup.select('a.b_acao[href], a[href*="produto"], a[href*="product"]'):
        add(node.get('href'))
    return links[:limit]


def wbuy_listing_products(base_url: str, html: str, limit: int = 1200) -> list[FastProductData]:
    soup = _soup(html)
    cards = _card_nodes(soup)
    category = _category(base_url, soup)
    products: list[FastProductData] = []
    seen: set[str] = set()
    for card in cards:
        product = _product_from_card(base_url, card, category)
        if not product:
            continue
        key = product.id_produto or product.codigo or product.url
        if not key or key in seen:
            continue
        seen.add(key)
        products.append(product)
        if len(products) >= limit:
            break
    if products:
        add_audit_event(
            'site_scraper_wbuy_category_cards_patch',
            area='SITE',
            step='entrada',
            status='OK',
            details={'products': len(products), 'cards': len(cards), 'category': category, 'responsible_file': RESPONSIBLE_FILE},
        )
    return products[:limit]


def install() -> None:
    from bling_app_zero.engines.fast_site_scraper import wbuy_parser

    wbuy_parser.wbuy_listing_products = wbuy_listing_products
    wbuy_parser.wbuy_product_links = wbuy_product_links
    runner = sys.modules.get('bling_app_zero.engines.fast_site_scraper.runner')
    if runner is not None:
        setattr(runner, 'wbuy_listing_products', wbuy_listing_products)


__all__ = ['install', 'wbuy_listing_products', 'wbuy_product_links']
