from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from bling_app_zero.core.text import normalize_key

MAX_REASONABLE_STOCK = 99999


@dataclass(frozen=True)
class PlatformStockProbeResult:
    quantity: str = ''
    confidence: str = 'baixa'
    source: str = ''
    platform: str = ''


def _clean_number(value: object) -> str:
    text = re.sub(r'\D+', '', str(value or ''))
    if not text:
        return ''
    try:
        number = int(text)
    except Exception:
        return ''
    if number < 0 or number > MAX_REASONABLE_STOCK:
        return ''
    return str(number)


def detect_platform(url: str = '', html: str = '') -> str:
    low = f'{url or ""} {html or ""}'.lower()
    host = urlparse(url or '').netloc.lower()
    if 'cdn.shopify.com' in low or 'shopify' in low or 'myshopify' in host:
        return 'shopify'
    if 'woocommerce' in low or 'wc_add_to_cart_params' in low or 'wp-content/plugins/woocommerce' in low:
        return 'woocommerce'
    if 'vtex' in low or 'checkout.vtex' in low or 'skujson' in low or '__runtime__' in low:
        return 'vtex'
    if 'nuvemshop' in low or 'tiendanube' in low or 'data-store' in low or 'ls.store' in low:
        return 'nuvemshop'
    if 'magento' in low or 'mage/' in low or 'x-magento' in low:
        return 'magento'
    if 'traycommerce' in low or 'tray.com.br' in low or 'loja tray' in low:
        return 'tray'
    return ''


def _best_quantity(values: list[object]) -> str:
    numbers: list[int] = []
    for value in values:
        number = _clean_number(value)
        if number != '':
            numbers.append(int(number))
    if not numbers:
        return ''
    positive = [n for n in numbers if n > 0]
    if positive:
        return str(max(positive))
    return '0'


def _extract_json_objects(raw: str, limit: int = 120) -> list[object]:
    objects: list[object] = []
    for candidate in re.findall(r'\{[^{}]{1,6000}\}', raw or '', flags=re.S)[:limit]:
        try:
            objects.append(json.loads(candidate))
        except Exception:
            continue
    return objects


def _walk_stock_values(data: object) -> list[object]:
    values: list[object] = []
    queue = [data]
    keys = {
        'stock', 'estoque', 'saldo', 'quantity', 'qty', 'inventory', 'inventoryquantity',
        'availablequantity', 'available_quantity', 'stockquantity', 'stock_quantity',
        'stocklevel', 'stock_level', 'maxquantity', 'max_quantity', 'available', 'availability',
    }
    while queue:
        item = queue.pop(0)
        if isinstance(item, dict):
            for key, value in item.items():
                key_norm = normalize_key(key).replace(' ', '').replace('_', '')
                if key_norm in {k.replace('_', '') for k in keys}:
                    values.append(value)
                if isinstance(value, (dict, list)):
                    queue.append(value)
        elif isinstance(item, list):
            queue.extend(item)
    return values


def probe_embedded_json(url: str, html: str) -> PlatformStockProbeResult:
    platform = detect_platform(url, html)
    values: list[object] = []
    key_pattern = re.compile(
        r'["\'](?:stock|estoque|saldo|quantity|qty|inventory|inventoryQuantity|availableQuantity|stockQuantity|stockLevel|maxQuantity)["\']\s*[:=]\s*["\']?(\d{1,7})',
        flags=re.I,
    )
    values.extend(key_pattern.findall(html or ''))
    for data in _extract_json_objects(html):
        values.extend(_walk_stock_values(data))
    quantity = _best_quantity(values)
    if quantity != '':
        return PlatformStockProbeResult(quantity, 'alta', 'embedded_json', platform)
    return PlatformStockProbeResult(platform=platform)


def probe_dom_limits(url: str, html: str) -> PlatformStockProbeResult:
    platform = detect_platform(url, html)
    soup = BeautifulSoup(html or '', 'html.parser')
    values: list[object] = []
    attrs = [
        'data-stock', 'data-estoque', 'data-quantity', 'data-qty', 'data-inventory',
        'data-max', 'max', 'stock', 'estoque', 'quantity', 'qty', 'inventory', 'content', 'value',
    ]
    selectors = [
        '[data-stock]', '[data-estoque]', '[data-quantity]', '[data-qty]', '[data-inventory]',
        '[data-max]', 'input[max]', '[class*=stock]', '[class*=estoque]', '[id*=stock]', '[id*=estoque]',
        '[class*=quantity]', '[id*=quantity]', '[itemprop=availability]',
    ]
    for selector in selectors:
        for node in soup.select(selector):
            for attr in attrs:
                if node.get(attr) is not None:
                    values.append(node.get(attr))
            text = node.get_text(' ', strip=True)
            values.extend(re.findall(r'\b\d{1,7}\b', text or ''))
    quantity = _best_quantity(values)
    if quantity != '':
        return PlatformStockProbeResult(quantity, 'media', 'dom_limits', platform)
    return PlatformStockProbeResult(platform=platform)


def probe_visible_text(url: str, html: str, text: str = '') -> PlatformStockProbeResult:
    platform = detect_platform(url, html)
    full = f'{html or ""} {text or ""}'
    patterns = [
        r'(?:estoque|saldo|quantidade|qtd)\s*(?:dispon[ií]vel)?\s*[:\-]?\s*(\d{1,7})',
        r'(?:restam|resta|apenas|somente)\s*(\d{1,7})',
        r'(\d{1,7})\s*(?:unidades|unidade|peças|pecas)\s*(?:em estoque|dispon[ií]veis)',
    ]
    for pattern in patterns:
        match = re.search(pattern, full, flags=re.I)
        if match:
            quantity = _clean_number(match.group(1))
            if quantity != '':
                return PlatformStockProbeResult(quantity, 'media', 'visible_text', platform)
    normalized = normalize_key(full)
    if any(term in normalized for term in ['sem estoque', 'indisponivel', 'esgotado', 'fora de estoque']):
        return PlatformStockProbeResult('0', 'alta', 'out_of_stock_text', platform)
    return PlatformStockProbeResult(platform=platform)


def probe_platform_stock(url: str, html: str, text: str = '') -> PlatformStockProbeResult:
    for result in [
        probe_embedded_json(url, html),
        probe_dom_limits(url, html),
        probe_visible_text(url, html, text),
    ]:
        if result.quantity != '':
            return result
    return PlatformStockProbeResult(platform=detect_platform(url, html))
