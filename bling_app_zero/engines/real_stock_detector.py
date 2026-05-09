from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from bling_app_zero.core.text import normalize_key
from bling_app_zero.engines.platform_stock_probe import probe_platform_stock

OUT_STOCK_TERMS = [
    'sem estoque', 'indisponivel', 'indisponível', 'esgotado', 'fora de estoque',
    'outofstock', 'out_of_stock', 'soldout', 'sold_out', 'unavailable', 'não disponível', 'nao disponivel',
]

IN_STOCK_TERMS = [
    'em estoque', 'disponivel', 'disponível', 'comprar', 'adicionar ao carrinho',
    'add to cart', 'instock', 'in_stock', 'available',
]

STOCK_PATTERNS = [
    r'["\'](?:stock|estoque|inventory|quantity|qty|saldo|available_quantity|availableQuantity|stockQuantity|stockLevel|inventoryQuantity)["\']\s*[:=]\s*["\']?(\d{1,7})',
    r'(?:estoque|saldo|quantidade|qtd)\s*(?:dispon[ií]vel)?\s*[:\-]?\s*(\d{1,7})',
    r'(?:restam|resta|apenas|somente)\s*(\d{1,7})',
    r'(\d{1,7})\s*(?:unidades|unidade|peças|pecas)\s*(?:em estoque|dispon[ií]veis)',
]

PLATFORM_HINTS = {
    'shopify': ['cdn.shopify.com', 'Shopify.theme', 'myshopify', '/cart/add.js', '/products/'],
    'woocommerce': ['woocommerce', 'wc_add_to_cart_params', 'add-to-cart', 'wp-content/plugins/woocommerce'],
    'nuvemshop': ['nuvemshop', 'tiendanube', 'LS.store', 'data-store'],
    'vtex': ['vtex', '__RUNTIME__', 'skuJson', 'productId', 'checkout.vtex'],
    'tray': ['tray.com.br', 'traycommerce', 'variant-stock', 'loja tray'],
    'magento': ['Magento_', 'mage/', 'x-magento', 'stock_status'],
}


@dataclass(frozen=True)
class StockDetection:
    quantity: str
    confidence: str
    source: str
    platform: str = ''


def _digits(value: object) -> str:
    text = re.sub(r'\D+', '', str(value or ''))
    if not text:
        return ''
    try:
        return str(int(text))
    except Exception:
        return text


def _platform_from_html(url: str, html: str) -> str:
    full = f'{url or ""} {html or ""}'
    low = full.lower()
    for platform, hints in PLATFORM_HINTS.items():
        if any(hint.lower() in low for hint in hints):
            return platform
    host = urlparse(url or '').netloc.lower()
    if 'shopify' in host:
        return 'shopify'
    if 'vtex' in host:
        return 'vtex'
    return ''


def _json_values(data: object) -> list[object]:
    values: list[object] = []
    queue = [data]
    keys = {
        'stock', 'estoque', 'inventory', 'quantity', 'qty', 'saldo',
        'available quantity', 'availablequantity', 'stock quantity', 'stockquantity',
        'stocklevel', 'inventoryquantity', 'inventory quantity', 'max quantity', 'maxquantity',
    }
    normalized_keys = {k.replace(' ', '') for k in keys}
    while queue:
        item = queue.pop(0)
        if isinstance(item, dict):
            for key, value in item.items():
                key_norm = normalize_key(key).replace(' ', '')
                if key_norm in normalized_keys:
                    values.append(value)
                if isinstance(value, (dict, list)):
                    queue.append(value)
        elif isinstance(item, list):
            queue.extend(item)
    return values


def detect_stock_from_json(html: str) -> StockDetection:
    for match in re.finditer(r'<script[^>]*>(.*?)</script>', html or '', flags=re.I | re.S):
        raw = match.group(1) or ''
        if not any(term in raw.lower() for term in ['stock', 'estoque', 'inventory', 'quantity', 'saldo']):
            continue
        for value in re.findall(r'(?:stock|estoque|inventory|quantity|qty|saldo|availableQuantity|stockQuantity|stockLevel|inventoryQuantity)["\']?\s*[:=]\s*["\']?(\d{1,7})', raw, flags=re.I):
            number = _digits(value)
            if number:
                return StockDetection(number, 'alta', 'json/script')
        candidates = re.findall(r'\{[^{}]{0,4000}\}', raw, flags=re.S)
        for candidate in candidates[:80]:
            try:
                data = json.loads(candidate)
            except Exception:
                continue
            for value in _json_values(data):
                number = _digits(value)
                if number:
                    return StockDetection(number, 'alta', 'json')
    return StockDetection('', 'baixa', '')


def detect_stock_from_dom(html: str, text: str = '') -> StockDetection:
    soup = BeautifulSoup(html or '', 'html.parser')
    selectors = [
        '[data-stock]', '[data-estoque]', '[data-quantity]', '[data-qty]', '[data-inventory]',
        '[itemprop=availability]', '[class*=stock]', '[class*=estoque]', '[id*=stock]', '[id*=estoque]', '[class*=quantity]', '[id*=quantity]',
    ]
    for selector in selectors:
        for node in soup.select(selector):
            for attr in ['data-stock', 'data-estoque', 'data-quantity', 'data-qty', 'data-inventory', 'content', 'value', 'max']:
                value = node.get(attr)
                number = _digits(value)
                if number:
                    return StockDetection(number, 'alta', f'dom:{attr}')
            node_text = node.get_text(' ', strip=True)
            for pattern in STOCK_PATTERNS:
                found = re.search(pattern, node_text, flags=re.I)
                if found:
                    return StockDetection(_digits(found.group(1)), 'media', 'dom/text')

    full_text = f'{html or ""} {text or ""}'
    for pattern in STOCK_PATTERNS:
        found = re.search(pattern, full_text, flags=re.I)
        if found:
            return StockDetection(_digits(found.group(1)), 'media', 'page/text')
    return StockDetection('', 'baixa', '')


def detect_stock_status(html: str, text: str = '') -> StockDetection:
    full = normalize_key(f'{html or ""} {text or ""}')
    if any(normalize_key(term) in full for term in OUT_STOCK_TERMS):
        return StockDetection('0', 'alta', 'status/out')
    if any(normalize_key(term) in full for term in IN_STOCK_TERMS):
        return StockDetection('', 'baixa', 'status/in')
    return StockDetection('', 'baixa', '')


def detect_platform_stock(url: str, html: str, text: str = '') -> StockDetection:
    safe_probe = probe_platform_stock(url, html, text)
    if safe_probe.quantity:
        return StockDetection(safe_probe.quantity, safe_probe.confidence, safe_probe.source, safe_probe.platform)

    platform = _platform_from_html(url, html)
    if not platform:
        return StockDetection('', 'baixa', '')

    json_result = detect_stock_from_json(html)
    if json_result.quantity:
        return StockDetection(json_result.quantity, json_result.confidence, f'{platform}:{json_result.source}', platform)

    dom_result = detect_stock_from_dom(html, text)
    if dom_result.quantity:
        return StockDetection(dom_result.quantity, dom_result.confidence, f'{platform}:{dom_result.source}', platform)

    status_result = detect_stock_status(html, text)
    if status_result.quantity == '0':
        return StockDetection('0', 'alta', f'{platform}:{status_result.source}', platform)

    return StockDetection('', 'baixa', f'{platform}:sem_quantidade', platform)


def detect_real_stock_detail(url: str = '', html: str = '', text: str = '') -> StockDetection:
    platform_result = detect_platform_stock(url, html, text)
    if platform_result.quantity:
        return platform_result

    json_result = detect_stock_from_json(html)
    if json_result.quantity:
        return json_result

    dom_result = detect_stock_from_dom(html, text)
    if dom_result.quantity:
        return dom_result

    return detect_stock_status(html, text)


def detect_real_stock(html: str, text: str = '', url: str = '') -> str:
    return detect_real_stock_detail(url=url, html=html, text=text).quantity
