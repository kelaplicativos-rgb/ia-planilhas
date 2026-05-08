from __future__ import annotations

import json

from bs4 import BeautifulSoup

from bling_app_zero.core.text import clean_cell
from bling_app_zero.engines.fast_site_scraper.models import FastProductPage


def _jsonld_items(data: object) -> list[dict]:
    queue = data if isinstance(data, list) else [data]
    items: list[dict] = []
    while queue:
        item = queue.pop(0)
        if isinstance(item, list):
            queue.extend(item)
            continue
        if not isinstance(item, dict):
            continue
        type_text = str(item.get('@type') or item.get('type') or '').lower()
        if 'product' in type_text or ('offers' in item and 'name' in item):
            items.append(item)
        for value in item.values():
            if isinstance(value, (dict, list)):
                queue.append(value)
    return items


def extract_jsonld_products(soup: BeautifulSoup) -> list[dict]:
    products: list[dict] = []
    for script in soup.find_all('script', type='application/ld+json'):
        raw = script.string or script.get_text() or ''
        if not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except Exception:
            continue
        products.extend(_jsonld_items(data))
    return products


def parse_product_page(url: str, html: str) -> FastProductPage:
    soup = BeautifulSoup(html or '', 'html.parser')
    text = clean_cell(soup.get_text(' ', strip=True))
    return FastProductPage(
        url=url,
        html=html or '',
        text=text,
        jsonld_products=extract_jsonld_products(soup),
    )


def soup_from_page(page: FastProductPage) -> BeautifulSoup:
    return BeautifulSoup(page.html or '', 'html.parser')
