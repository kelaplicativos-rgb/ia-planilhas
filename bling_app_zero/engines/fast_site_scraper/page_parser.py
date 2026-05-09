from __future__ import annotations

import json
import re

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
        type_value = item.get('@type') or item.get('type') or ''
        if isinstance(type_value, list):
            type_text = ' '.join(map(str, type_value)).lower()
        else:
            type_text = str(type_value).lower()
        if 'product' in type_text or ('offers' in item and 'name' in item):
            items.append(item)
        graph = item.get('@graph')
        if isinstance(graph, list):
            queue.extend(graph)
        for value in item.values():
            if isinstance(value, (dict, list)):
                queue.append(value)
    return items


def _clean_jsonld(raw: str) -> str:
    text = str(raw or '').strip()
    text = re.sub(r'^\s*<!--|-->\s*$', '', text)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.S)
    return text.strip()


def _load_jsonld(raw: str) -> object | None:
    text = _clean_jsonld(raw)
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        pass

    # Alguns sites deixam múltiplos objetos JSON-LD no mesmo script sem array.
    parts = re.findall(r'\{.*?\}(?=\s*\{|\s*$)', text, flags=re.S)
    decoded: list[object] = []
    for part in parts:
        try:
            decoded.append(json.loads(part))
        except Exception:
            continue
    return decoded or None


def extract_jsonld_products(soup: BeautifulSoup) -> list[dict]:
    products: list[dict] = []
    for script in soup.find_all('script', type='application/ld+json'):
        raw = script.string or script.get_text() or ''
        data = _load_jsonld(raw)
        if data is None:
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
