from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

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
    """Extrai dados mínimos dos cards wBuy quando os detalhes falham.

    A página de vitrine wBuy costuma trazer URL, SKU, nome, preço e imagem nos
    cards. Isso evita lote vazio quando a leitura das páginas de detalhe é
    bloqueada ou fica lenta demais.
    """
    if not is_wbuy_html(html) and 'data-sku=' not in str(html or '').lower():
        return []
    soup = _soup(html)
    products: list[FastProductData] = []
    seen: set[str] = set()

    for card in _card_nodes(soup):
        action = card.select_one('a.b_acao[href]') or card.select_one('a[href]')
        href = action.get('href') if action else ''
        url = _norm_url(urljoin(base_url, str(href or '').strip()))
        if not url or not _allowed_product_url(url, base_url):
            continue

        sku = clean_cell(card.get('data-sku') or '')
        code = sku or clean_cell(card.get('data-id') or '')
        key = sku or url
        if key in seen:
            continue
        seen.add(key)

        name_node = card.select_one('h3.produto, .produto, [itemprop="name"]')
        image_node = card.select_one('img[data-src], img[src]')
        price_node = card.select_one('.valor_final') or card.select_one('.valor')
        name = clean_cell(
            (name_node.get('title') if name_node else '')
            or (name_node.get_text(' ', strip=True) if name_node else '')
            or (image_node.get('alt') if image_node else '')
        )[:240]
        image = clean_cell(urljoin(base_url, str((image_node.get('data-src') or image_node.get('src') or '') if image_node else '').strip()))
        price = _clean_price(price_node.get_text(' ', strip=True) if price_node else '')

        products.append(FastProductData(
            url=url,
            codigo=code,
            descricao=name,
            preco=price,
            imagem=image,
        ))
        if len(products) >= limit:
            break

    return products[:limit]


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