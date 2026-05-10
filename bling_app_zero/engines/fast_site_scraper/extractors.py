from __future__ import annotations

import re
from urllib.parse import urljoin

from bling_app_zero.core.gtin import clean_gtin
from bling_app_zero.core.text import clean_cell, normalize_key
from bling_app_zero.engines.brand_title_detector import detect_brand_from_title
from bling_app_zero.engines.fast_site_scraper.block_scraper import scrape_product_blocks
from bling_app_zero.engines.fast_site_scraper.models import FastProductPage
from bling_app_zero.engines.fast_site_scraper.page_parser import soup_from_page
from bling_app_zero.engines.real_stock_detector import OUT_STOCK_TERMS, detect_real_stock


def _first_product(page: FastProductPage) -> dict:
    return page.jsonld_products[0] if page.jsonld_products else {}


def _offer(product: dict) -> dict:
    offers = product.get('offers') if isinstance(product, dict) else None
    if isinstance(offers, list) and offers:
        return offers[0] if isinstance(offers[0], dict) else {}
    return offers if isinstance(offers, dict) else {}


def _as_absolute_url(page_url: str, value: object) -> str:
    text = clean_cell(value or '')
    if not text:
        return ''
    return urljoin(page_url, text)


def _first_from_srcset(value: object) -> str:
    text = clean_cell(value or '')
    if not text:
        return ''
    first = text.split(',')[0].strip()
    return first.split()[0].strip() if first else ''


def _clean_price(value: object) -> str:
    text = clean_cell(value or '')
    if not text:
        return ''
    match = re.search(r'(?:R\$\s*)?([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2}|[0-9]+(?:[\.,][0-9]{2})?)', text)
    return match.group(1) if match else text[:40]


def _join_unique(values: list[str], limit: int = 5000) -> str:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = clean_cell(value)
        key = normalize_key(text)
        if not text or not key or key in seen:
            continue
        seen.add(key)
        result.append(text)
    return ' • '.join(result)[:limit]


def extract_url(page: FastProductPage) -> str:
    product = _first_product(page)
    return clean_cell(product.get('url') or page.url) if product else page.url


def extract_description(page: FastProductPage) -> str:
    product = _first_product(page)
    if product:
        value = clean_cell(product.get('name') or '')
        if value:
            return value[:240]
    soup = soup_from_page(page)
    for selector in ['h1', '[itemprop=name]', '.product-name', '.nome', '.name', '.titulo', '.title']:
        node = soup.select_one(selector)
        if node:
            value = clean_cell(node.get_text(' ', strip=True))
            if value:
                return value[:240]
    meta = soup.find('meta', property='og:title')
    if meta and meta.get('content'):
        return clean_cell(meta.get('content'))[:240]
    if soup.title:
        return clean_cell(soup.title.get_text(' ', strip=True))[:240]
    return ''


def extract_description_complementar(page: FastProductPage) -> str:
    product = _first_product(page)
    jsonld_description = clean_cell(product.get('description') or '') if product else ''
    blocks = scrape_product_blocks(page)
    title_key = normalize_key(extract_description(page))
    values: list[str] = []
    for value in [blocks.complementary_description, blocks.attributes, blocks.technical_sheet, jsonld_description]:
        text = clean_cell(value)
        if text and normalize_key(text) != title_key:
            values.append(text)
    return _join_unique(values, limit=5000)


def extract_ficha_tecnica(page: FastProductPage) -> str:
    blocks = scrape_product_blocks(page)
    return clean_cell(blocks.technical_sheet or blocks.attributes or blocks.all_blocks)[:3500]


def extract_caracteristicas(page: FastProductPage) -> str:
    blocks = scrape_product_blocks(page)
    return clean_cell(blocks.attributes or blocks.complementary_description or blocks.all_blocks)[:3500]


def extract_brand(page: FastProductPage) -> str:
    product = _first_product(page)
    title = extract_description(page)
    brand = product.get('brand') if product else None

    if isinstance(brand, dict):
        value = clean_cell(brand.get('name') or '')
        if value:
            return detect_brand_from_title(title, fallback=value)

    value = clean_cell(brand or '')
    if value:
        return detect_brand_from_title(title, fallback=value)

    soup = soup_from_page(page)
    for selector in ['[itemprop=brand]', '.brand', '.marca', '[class*=brand]', '[class*=marca]']:
        node = soup.select_one(selector)
        if node:
            detected = clean_cell(node.get('content') or node.get_text(' ', strip=True))
            if detected:
                return detect_brand_from_title(title, fallback=detected)

    return detect_brand_from_title(title)


def extract_price(page: FastProductPage) -> str:
    product = _first_product(page)
    offer = _offer(product)
    value = _clean_price(offer.get('price') or '')
    if value:
        return value

    price_spec = offer.get('priceSpecification') if isinstance(offer, dict) else None
    if isinstance(price_spec, dict):
        value = _clean_price(price_spec.get('price') or '')
        if value:
            return value

    soup = soup_from_page(page)
    for selector in ['meta[property="product:price:amount"]', 'meta[itemprop=price]', '[itemprop=price]', '[class*=price]', '[class*=preco]', '[class*=preço]']:
        node = soup.select_one(selector)
        if not node:
            continue
        value = _clean_price(node.get('content') or node.get_text(' ', strip=True))
        if value:
            return value

    text = page.text
    match = re.search(r'R\$\s*([0-9\.]+,[0-9]{2})', text)
    if match:
        return match.group(1)
    match = re.search(r'\b([0-9]{1,3}(?:\.[0-9]{3})*,[0-9]{2})\b', text)
    return match.group(1) if match else ''


def extract_stock(page: FastProductPage) -> str:
    product = _first_product(page)
    offer = _offer(product)
    availability = normalize_key(offer.get('availability', '')) if offer else ''
    if any(normalize_key(term) in availability for term in OUT_STOCK_TERMS):
        return '0'

    real_stock = detect_real_stock(page.html, page.text, url=page.url)
    if real_stock != '':
        return real_stock

    key = normalize_key(f'{page.html} {page.text}')
    if any(normalize_key(term) in key for term in OUT_STOCK_TERMS):
        return '0'
    return ''


def extract_images(page: FastProductPage, limit: int = 12) -> str:
    product = _first_product(page)
    image = product.get('image') if product else None
    urls: list[str] = []

    def add(value: object) -> None:
        url = _as_absolute_url(page.url, value)
        if not url:
            return
        low = url.lower()
        if any(term in low for term in ['logo', 'sprite', 'placeholder', 'icon', 'whatsapp', 'facebook.com/tr', 'blank.gif']):
            return
        if url not in urls:
            urls.append(url)

    if isinstance(image, list):
        for item in image:
            if isinstance(item, dict):
                add(item.get('url') or item.get('contentUrl'))
            else:
                add(item)
    elif isinstance(image, dict):
        add(image.get('url') or image.get('contentUrl'))
    else:
        add(image)

    soup = soup_from_page(page)
    for meta_selector in ['meta[property="og:image"]', 'meta[property="og:image:secure_url"]', 'link[rel="image_src"]']:
        node = soup.select_one(meta_selector)
        if node:
            add(node.get('content') or node.get('href'))

    for img in soup.find_all('img'):
        src = (
            img.get('src')
            or img.get('data-src')
            or img.get('data-lazy')
            or img.get('data-original')
            or img.get('data-zoom-image')
            or _first_from_srcset(img.get('srcset') or img.get('data-srcset'))
        )
        add(src)
        if len(urls) >= limit:
            break
    return '|'.join(urls[:limit])


def extract_code(page: FastProductPage) -> str:
    product = _first_product(page)
    if product:
        value = clean_cell(product.get('sku') or product.get('mpn') or product.get('productID') or '')
        if value:
            return value
    match = re.search(r'(?:SKU|COD|CÓD|Código|Codigo|REF|Referência|Modelo)[:\s#-]+([A-Za-z0-9._/-]+)', page.text, flags=re.I)
    return clean_cell(match.group(1)) if match else ''


def extract_gtin(page: FastProductPage) -> str:
    product = _first_product(page)
    if product:
        for key in ['gtin', 'gtin8', 'gtin12', 'gtin13', 'gtin14', 'ean']:
            value = clean_gtin(product.get(key) or '')
            if value:
                return value
    match = re.search(r'(?:GTIN|EAN|Código de barras|Codigo de barras)[:\s#-]+([0-9 .-]{8,20})', page.text, flags=re.I)
    if match:
        return clean_gtin(match.group(1))
    match = re.search(r'\b(\d{8}|\d{12}|\d{13}|\d{14})\b', page.text)
    return clean_gtin(match.group(1)) if match else ''


def extract_category(page: FastProductPage) -> str:
    product = _first_product(page)
    value = clean_cell(product.get('category') or '') if product else ''
    if value:
        return value
    soup = soup_from_page(page)
    crumbs: list[str] = []
    for selector in ['.breadcrumb a', '.breadcrumbs a', '[aria-label*=breadcrumb] a', '[class*=breadcrumb] a']:
        for node in soup.select(selector):
            text = clean_cell(node.get_text(' ', strip=True))
            if text and normalize_key(text) not in {'home', 'inicio', 'início'} and text not in crumbs:
                crumbs.append(text)
    return ' > '.join(crumbs)
