from __future__ import annotations

import json
import os
import re
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.text import clean_cell, normalize_key
from bling_app_zero.engines.fast_site_scraper.models import FastProductData, FastProductPage

WBUY_HINTS = (
    'sistemawbuy.com.br',
    'wbuy lojas virtuais',
    'produtos_autocomplete.php',
    'data-produtoid=',
    'id="inc_sku"',
    'class="codigo_produto"',
)

WBUY_BLOCKED_URL_TERMS = (
    '/login', '/conta', '/checkout', '/cart', '/carrinho', '/blog', '/politica', '/termos',
    'facebook', 'instagram', 'youtube', 'whatsapp', 'mailto:', 'tel:', '#',
)

GENERIC_CARD_SELECTORS = (
    '[data-sku]',
    '[data-product-id]',
    '[data-produtoid]',
    '[data-id]',
    '[itemtype*="schema.org/Product"]',
    '.product',
    '.produto',
    '.prod',
    '.item-produto',
    '.product-item',
    '.produto-item',
    'article',
)

RESPONSIBLE_FILE = 'bling_app_zero/engines/fast_site_scraper/wbuy_parser.py'
OPENAI_RESPONSES_URL = 'https://api.openai.com/v1/responses'
DEFAULT_OPENAI_MODEL = 'gpt-4.1'


def is_wbuy_html(html: str) -> bool:
    text = str(html or '').lower()
    return any(hint in text for hint in WBUY_HINTS)


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or '', 'html.parser')


def _norm_url(url: str) -> str:
    parsed = urlparse(str(url or '').strip())
    if not parsed.scheme or not parsed.netloc:
        return ''
    clean = parsed._replace(fragment='', path=re.sub(r'/+', '/', parsed.path or '/'))
    return urlunparse(clean).rstrip('/')


def _same_domain(url: str, base: str) -> bool:
    host = urlparse(url).netloc.lower().replace('www.', '')
    root = urlparse(base).netloc.lower().replace('www.', '')
    return bool(host and root and (host == root or host.endswith('.' + root)))


def _allowed_product_url(url: str, base_url: str) -> bool:
    low = str(url or '').lower()
    return (
        url.startswith(('http://', 'https://'))
        and _same_domain(url, base_url)
        and not any(term in low for term in WBUY_BLOCKED_URL_TERMS)
        and not re.search(r'\.(jpg|jpeg|png|webp|gif|svg|css|js|pdf|zip|rar)(\?|$)', low)
    )


def _append_unique(values: list[str], value: str, limit: int = 0) -> None:
    text = clean_cell(value)
    if text and text not in values and (not limit or len(values) < limit):
        values.append(text)


def _clean_price(value: object) -> str:
    text = clean_cell(value or '')
    if not text:
        return ''
    matches = re.findall(r'(?:R\$\s*)?([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+(?:[\.,][0-9]{2})?)', text)
    return matches[-1] if matches else text[:40]


def _card_nodes(soup: BeautifulSoup) -> list:
    nodes: list = []
    for selector in [
        '.prod .item[data-id][data-sku]',
        '.produtos .item[data-id][data-sku]',
        '.item[data-id][data-sku]',
    ]:
        for card in soup.select(selector):
            if card not in nodes:
                nodes.append(card)
    return nodes


def _generic_card_nodes(soup: BeautifulSoup) -> list:
    nodes: list = []
    for selector in GENERIC_CARD_SELECTORS:
        for card in soup.select(selector):
            if card not in nodes:
                nodes.append(card)
            if len(nodes) >= 900:
                return nodes
    return nodes


def _first_href(card, base_url: str) -> str:
    for selector in ['a.b_acao[href]', 'a[href*="produto"]', 'a[href*="product"]', 'a[href]']:
        node = card.select_one(selector)
        if not node:
            continue
        url = _norm_url(urljoin(base_url, str(node.get('href') or '').strip()))
        if url and _allowed_product_url(url, base_url):
            return url
    return ''


def _image_url(card, base_url: str) -> str:
    node = card.select_one('img[data-src], img[data-original], img[data-lazy], img[src], source[srcset]')
    if not node:
        return ''
    raw = node.get('data-src') or node.get('data-original') or node.get('data-lazy') or node.get('src') or node.get('srcset') or ''
    raw = str(raw).split(',')[0].split()[0].strip()
    url = clean_cell(urljoin(base_url, raw))
    low = url.lower()
    if any(term in low for term in ['logo', 'sprite', 'placeholder', 'icon', 'whatsapp', 'facebook.com/tr', 'blank.gif']):
        return ''
    return url


def _product_from_card(base_url: str, card) -> FastProductData | None:
    url = _first_href(card, base_url)
    if not url:
        return None

    sku = clean_cell(card.get('data-sku') or card.get('data-codigo') or card.get('data-code') or '')
    code = sku or clean_cell(card.get('data-id') or card.get('data-product-id') or card.get('data-produtoid') or '')
    image = _image_url(card, base_url)
    name_node = card.select_one('h3.produto, h2, h3, [itemprop="name"], .product-name, .produto, .name, .title')
    image_node = card.select_one('img[alt]')
    name = clean_cell(
        (name_node.get('title') if name_node else '')
        or (name_node.get_text(' ', strip=True) if name_node else '')
        or (image_node.get('alt') if image_node else '')
    )[:240]
    price_node = card.select_one('.valor_final, .price, .preco, .preço, [class*="price"], [class*="preco"], [class*="valor"]')
    price = _clean_price(price_node.get_text(' ', strip=True) if price_node else card.get_text(' ', strip=True))

    if not name or not (price or image or code):
        return None
    return FastProductData(url=url, codigo=code, descricao=name, preco=price, imagem=image)


def _api_key_from_streamlit() -> str:
    try:
        import streamlit as st  # type: ignore
        value = st.secrets.get('openai', {}).get('api_key') if hasattr(st, 'secrets') else ''
        return str(value or '').strip()
    except Exception:
        return ''


def _openai_api_key() -> str:
    return (
        os.getenv('MAPEIAAI_OPENAI_API_KEY', '').strip()
        or os.getenv('OPENAI_API_KEY', '').strip()
        or _api_key_from_streamlit()
    )


def _response_text(payload: dict) -> str:
    text = payload.get('output_text')
    if isinstance(text, str) and text.strip():
        return text
    chunks: list[str] = []
    for item in payload.get('output') or []:
        if not isinstance(item, dict):
            continue
        for content in item.get('content') or []:
            if isinstance(content, dict) and isinstance(content.get('text'), str):
                chunks.append(content['text'])
    return ''.join(chunks).strip()


def _compact_html_for_ai(base_url: str, html: str, limit: int) -> str:
    soup = _soup(html)
    snippets: list[str] = []
    for card in _generic_card_nodes(soup):
        text = clean_cell(card.get_text(' ', strip=True))[:700]
        hrefs = []
        for node in card.select('a[href]')[:4]:
            href = _norm_url(urljoin(base_url, str(node.get('href') or '').strip()))
            if href and _allowed_product_url(href, base_url):
                _append_unique(hrefs, href, 4)
        images = []
        for node in card.select('img[data-src], img[src]')[:3]:
            _append_unique(images, _image_url(node, base_url), 3)
        attrs = {
            key: clean_cell(card.get(key) or '')
            for key in ['data-id', 'data-sku', 'data-product-id', 'data-produtoid']
            if clean_cell(card.get(key) or '')
        }
        if text or hrefs or images or attrs:
            snippets.append(json.dumps({'attrs': attrs, 'hrefs': hrefs, 'images': images, 'text': text}, ensure_ascii=False))
        if len(snippets) >= min(limit * 2, 80):
            break

    if not snippets:
        for node in soup.select('a[href]')[:160]:
            href = _norm_url(urljoin(base_url, str(node.get('href') or '').strip()))
            text = clean_cell(node.get_text(' ', strip=True))[:180]
            if href and text:
                snippets.append(json.dumps({'hrefs': [href], 'text': text}, ensure_ascii=False))
    return '\n'.join(snippets)[:55000]


def _openai_listing_products(base_url: str, html: str, limit: int) -> list[FastProductData]:
    key = _openai_api_key()
    if not key:
        return []

    compact = _compact_html_for_ai(base_url, html, limit)
    if not compact:
        return []

    schema = {
        'type': 'object',
        'additionalProperties': False,
        'properties': {
            'products': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'additionalProperties': False,
                    'properties': {
                        'url': {'type': 'string'},
                        'codigo': {'type': 'string'},
                        'gtin': {'type': 'string'},
                        'descricao': {'type': 'string'},
                        'preco': {'type': 'string'},
                        'estoque': {'type': 'string'},
                        'imagem': {'type': 'string'},
                        'marca': {'type': 'string'},
                        'categoria': {'type': 'string'},
                    },
                    'required': ['url', 'codigo', 'gtin', 'descricao', 'preco', 'estoque', 'imagem', 'marca', 'categoria'],
                },
            },
        },
        'required': ['products'],
    }
    prompt = (
        'Extraia produtos reais de uma página de fornecedor/e-commerce. '
        'Use apenas dados presentes nos snippets. Ignore menus, banners, login, carrinho e links sociais. '
        'Prefira preço final/promocional em vez de preço antigo. Retorne no máximo '
        f'{int(limit)} produtos. Base URL: {base_url}\n\nSNIPPETS:\n{compact}'
    )
    request_payload = {
        'model': os.getenv('MAPEIAAI_OPENAI_MODEL', DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL,
        'instructions': 'Você é um extrator de catálogo. Responda somente no JSON schema solicitado, sem comentários.',
        'input': prompt,
        'text': {
            'format': {
                'type': 'json_schema',
                'name': 'product_listing_extraction',
                'schema': schema,
                'strict': False,
            },
        },
        'temperature': 0,
    }

    try:
        response = requests.post(
            OPENAI_RESPONSES_URL,
            headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
            json=request_payload,
            timeout=28,
        )
        if response.status_code >= 400:
            add_audit_event(
                'site_scraper_openai_listing_fallback',
                area='SITE',
                step='entrada',
                status='AVISO',
                details={'status_code': response.status_code, 'products': 0, 'responsible_file': RESPONSIBLE_FILE},
            )
            return []
        raw_text = _response_text(response.json())
        data = json.loads(raw_text) if raw_text else {}
    except Exception as exc:
        add_audit_event(
            'site_scraper_openai_listing_fallback',
            area='SITE',
            step='entrada',
            status='AVISO',
            details={'error': type(exc).__name__, 'products': 0, 'responsible_file': RESPONSIBLE_FILE},
        )
        return []

    products: list[FastProductData] = []
    seen: set[str] = set()
    for item in data.get('products') or []:
        if not isinstance(item, dict):
            continue
        url = _norm_url(urljoin(base_url, clean_cell(item.get('url') or '')))
        if not url or not _allowed_product_url(url, base_url):
            continue
        descricao = clean_cell(item.get('descricao') or '')[:240]
        key_value = clean_cell(item.get('codigo') or '') or url
        if not descricao or key_value in seen:
            continue
        seen.add(key_value)
        products.append(FastProductData(
            url=url,
            codigo=clean_cell(item.get('codigo') or ''),
            gtin=clean_cell(item.get('gtin') or ''),
            descricao=descricao,
            preco=_clean_price(item.get('preco') or ''),
            estoque=clean_cell(item.get('estoque') or ''),
            imagem=clean_cell(urljoin(base_url, clean_cell(item.get('imagem') or ''))),
            marca=clean_cell(item.get('marca') or ''),
            categoria=clean_cell(item.get('categoria') or ''),
        ))
        if len(products) >= limit:
            break

    add_audit_event(
        'site_scraper_openai_listing_fallback',
        area='SITE',
        step='entrada',
        status='OK' if products else 'INFO',
        details={'products': len(products), 'responsible_file': RESPONSIBLE_FILE},
    )
    return products[:limit]


def wbuy_product_links(base_url: str, html: str, limit: int = 1200) -> list[str]:
    if not is_wbuy_html(html) and 'data-sku=' not in str(html or '').lower():
        return []
    soup = _soup(html)
    links: list[str] = []

    def add(href: object) -> None:
        url = _norm_url(urljoin(base_url, str(href or '').strip()))
        if url and _allowed_product_url(url, base_url) and url not in links and len(links) < limit:
            links.append(url)

    for card in _card_nodes(soup):
        action = card.select_one('a.b_acao[href]') or card.select_one('a[href]')
        if action:
            add(action.get('href'))

    for node in soup.select('a.b_acao[href]'):
        add(node.get('href'))

    return links[:limit]


def wbuy_listing_products(base_url: str, html: str, limit: int = 1200) -> list[FastProductData]:
    """Extrai dados de cards de vitrine; usa IA opcional se o HTML variar."""
    soup = _soup(html)
    products: list[FastProductData] = []
    seen: set[str] = set()
    preferred_cards = _card_nodes(soup) if is_wbuy_html(html) or 'data-sku=' in str(html or '').lower() else []
    cards = preferred_cards or _generic_card_nodes(soup)

    for card in cards:
        product = _product_from_card(base_url, card)
        if not product:
            continue
        key = product.codigo or product.url
        if not key or key in seen:
            continue
        seen.add(key)
        products.append(product)
        if len(products) >= limit:
            break

    if products:
        return products[:limit]
    return _openai_listing_products(base_url, html, limit)


def html_has_wbuy_product(html: str) -> bool:
    if not is_wbuy_html(html):
        return False
    soup = _soup(html)
    return bool(
        soup.select_one('[itemtype*="schema.org/Product"]')
        or soup.select_one('#produto .nome_produto')
        or soup.select_one('meta[itemprop="sku"]')
        or soup.select_one('.codigo_produto')
    )


def _content(soup: BeautifulSoup, selector: str, attr: str = 'content') -> str:
    node = soup.select_one(selector)
    if not node:
        return ''
    return clean_cell(node.get(attr) or node.get_text(' ', strip=True))


def _page_soup(page: FastProductPage) -> BeautifulSoup:
    return _soup(page.html)


def wbuy_product_url(page: FastProductPage) -> str:
    if not is_wbuy_html(page.html):
        return ''
    soup = _page_soup(page)
    return clean_cell(
        _content(soup, 'link[itemprop="url"]', 'href')
        or _content(soup, 'meta[property="og:url"]')
        or _content(soup, 'link[rel="canonical"]', 'href')
        or page.url
    )


def wbuy_product_name(page: FastProductPage) -> str:
    if not is_wbuy_html(page.html):
        return ''
    soup = _page_soup(page)
    value = clean_cell(
        _content(soup, '#produto .nome_produto')
        or _content(soup, '.nome_produto')
        or _content(soup, '[itemtype*="schema.org/Product"] [itemprop="name"]')
        or _content(soup, 'meta[property="og:title"]')
    )
    value = re.sub(r'^comprar\s+', '', value, flags=re.I).strip()
    value = re.sub(r'\s+-\s+R\$\s*[0-9\.]+,[0-9]{2}\s*$', '', value, flags=re.I).strip()
    return value[:240]


def wbuy_product_sku(page: FastProductPage) -> str:
    if not is_wbuy_html(page.html):
        return ''
    soup = _page_soup(page)
    return clean_cell(
        _content(soup, 'meta[itemprop="sku"]')
        or _content(soup, '.cor_primaria.active[data-sku]', 'data-sku')
        or _content(soup, '.cor_primaria[data-sku]', 'data-sku')
        or _content(soup, '[data-sku]', 'data-sku')
    )


def wbuy_product_mpn(page: FastProductPage) -> str:
    if not is_wbuy_html(page.html):
        return ''
    soup = _page_soup(page)
    value = _content(soup, '[itemprop="identifier"][content^="mpn:"]')
    if value.lower().startswith('mpn:'):
        return clean_cell(value.split(':', 1)[1])
    match = re.search(r'\bC[oó]d\.?:\s*([A-Za-z0-9._/-]+)', page.text, flags=re.I)
    return clean_cell(match.group(1)) if match else ''


def wbuy_product_code(page: FastProductPage) -> str:
    return wbuy_product_sku(page) or wbuy_product_mpn(page)


def wbuy_product_brand(page: FastProductPage) -> str:
    if not is_wbuy_html(page.html):
        return ''
    soup = _page_soup(page)
    return clean_cell(
        _content(soup, '.codigo_produto .marca a')
        or _content(soup, '.marca a')
        or _content(soup, '[itemprop="brand"]')
    )


def wbuy_product_price(page: FastProductPage) -> str:
    if not is_wbuy_html(page.html):
        return ''
    soup = _page_soup(page)
    value = clean_cell(
        _content(soup, '.valores meta[itemprop="price"]')
        or _content(soup, 'meta[itemprop="price"]')
        or _content(soup, '.valores .valor span')
        or _content(soup, '.valores .valor')
    )
    if not value:
        return ''
    match = re.search(r'(?:R\$\s*)?([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+(?:[\.,][0-9]{2})?)', value)
    return match.group(1) if match else value[:40]


def wbuy_product_stock(page: FastProductPage) -> str:
    if not is_wbuy_html(page.html):
        return ''
    soup = _page_soup(page)
    availability = normalize_key(_content(soup, 'meta[itemprop="availability"]'))
    if any(term in availability for term in ['outofstock', 'out stock', 'esgotado', 'indisponivel']):
        return '0'
    qty = soup.select_one('input.quantidade[max], input[type="number"][max]')
    if qty:
        value = clean_cell(qty.get('max') or '')
        if re.fullmatch(r'\d+(?:[\.,]\d+)?', value):
            return value.replace(',', '.')
    return '10' if 'instock' in availability or 'in stock' in availability else ''


def wbuy_product_images(page: FastProductPage, limit: int = 12) -> list[str]:
    if not is_wbuy_html(page.html):
        return []
    soup = _page_soup(page)
    urls: list[str] = []

    def add(value: object) -> None:
        url = clean_cell(urljoin(page.url, str(value or '').strip()))
        if not url:
            return
        low = url.lower()
        if any(term in low for term in ['logo', 'sprite', 'placeholder', 'icon', 'whatsapp', 'facebook.com/tr', 'blank.gif']):
            return
        _append_unique(urls, url, limit)

    for node in soup.select('link[itemprop="image"][href]'):
        add(node.get('href'))
    for node in soup.select('#produto .fotos img, #produto img[data-src], #produto img[src]'):
        add(node.get('data-src') or node.get('src') or node.get('data-zoom-image'))
    node = soup.select_one('meta[property="og:image"]')
    if node:
        add(node.get('content'))
    return urls[:limit]


def wbuy_product_category(page: FastProductPage) -> str:
    if not is_wbuy_html(page.html):
        return ''
    soup = _page_soup(page)
    current = normalize_key(wbuy_product_name(page))
    crumbs: list[str] = []
    for node in soup.select('.breadcrumb [itemprop="name"], .breadcrumb a, [aria-label*=breadcrumb] a'):
        text = clean_cell(node.get_text(' ', strip=True))
        key = normalize_key(text)
        if not key or key in {'pagina inicial', 'home', 'inicio'} or key == current:
            continue
        if text not in crumbs:
            crumbs.append(text)
    return crumbs[0] if crumbs else ''


def wbuy_product_description(page: FastProductPage) -> str:
    if not is_wbuy_html(page.html):
        return ''
    soup = _page_soup(page)
    values: list[str] = []
    for selector in ['#produto .descricao .texto', '#produto [itemprop="description"]', '.descricao .texto', '.descricao']:
        node = soup.select_one(selector)
        if node:
            _append_unique(values, node.get_text(' ', strip=True))
    meta = _content(soup, 'meta[name="description"]') or _content(soup, 'meta[property="og:description"]')
    _append_unique(values, meta)
    return ' • '.join(values)[:5000]


__all__ = [
    'html_has_wbuy_product',
    'is_wbuy_html',
    'wbuy_listing_products',
    'wbuy_product_brand',
    'wbuy_product_category',
    'wbuy_product_code',
    'wbuy_product_description',
    'wbuy_product_images',
    'wbuy_product_links',
    'wbuy_product_mpn',
    'wbuy_product_name',
    'wbuy_product_price',
    'wbuy_product_sku',
    'wbuy_product_stock',
    'wbuy_product_url',
]