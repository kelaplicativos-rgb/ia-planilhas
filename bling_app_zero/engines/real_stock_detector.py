from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from bling_app_zero.core.text import normalize_key

OUT_STOCK_TERMS = [
    'sem estoque', 'indisponivel', 'indisponível', 'esgotado', 'fora de estoque',
    'outofstock', 'out_of_stock', 'soldout', 'sold_out', 'unavailable', 'não disponível', 'nao disponivel',
]

IN_STOCK_TERMS = [
    'em estoque', 'disponivel', 'disponível', 'comprar', 'adicionar ao carrinho',
    'add to cart', 'instock', 'in_stock', 'available',
]

STOCK_PATTERNS = [
    r'["\'](?:stock|estoque|inventory|quantity|qty|saldo|available_quantity|availableQuantity|stockQuantity)["\']\s*[:=]\s*["\']?(\d{1,7})',
    r'(?:estoque|saldo|quantidade|qtd)\s*(?:dispon[ií]vel)?\s*[:\-]?\s*(\d{1,7})',
    r'(?:restam|resta|apenas|somente)\s*(\d{1,7})',
    r'(\d{1,7})\s*(?:unidades|unidade|peças|pecas)\s*(?:em estoque|dispon[ií]veis)',
]

META_KEYS = [
    'product:availability', 'availability', 'og:availability', 'twitter:data1',
]


def _digits(value: object) -> str:
    text = re.sub(r'\D+', '', str(value or ''))
    if not text:
        return ''
    try:
        return str(int(text))
    except Exception:
        return text


def _json_values(data: object) -> list[object]:
    values: list[object] = []
    queue = [data]
    while queue:
        item = queue.pop(0)
        if isinstance(item, dict):
            for key, value in item.items():
                key_norm = normalize_key(key)
                if key_norm in {'stock', 'estoque', 'inventory', 'quantity', 'qty', 'saldo', 'available quantity', 'stock quantity'}:
                    values.append(value)
                if isinstance(value, (dict, list)):
                    queue.append(value)
        elif isinstance(item, list):
            queue.extend(item)
    return values


def detect_stock_from_json(html: str) -> str:
    for match in re.finditer(r'<script[^>]*>(.*?)</script>', html or '', flags=re.I | re.S):
        raw = match.group(1) or ''
        if not any(term in raw.lower() for term in ['stock', 'estoque', 'inventory', 'quantity', 'saldo']):
            continue
        candidates = re.findall(r'\{.*?\}', raw, flags=re.S)
        for candidate in candidates[:30]:
            try:
                data = json.loads(candidate)
            except Exception:
                continue
            for value in _json_values(data):
                number = _digits(value)
                if number:
                    return number
    return ''


def detect_stock_from_dom(html: str, text: str = '') -> str:
    soup = BeautifulSoup(html or '', 'html.parser')
    for selector in [
        '[data-stock]', '[data-estoque]', '[data-quantity]', '[data-qty]',
        '[itemprop=availability]', '[class*=stock]', '[class*=estoque]', '[id*=stock]', '[id*=estoque]',
    ]:
        for node in soup.select(selector):
            for attr in ['data-stock', 'data-estoque', 'data-quantity', 'data-qty', 'content', 'value']:
                value = node.get(attr)
                number = _digits(value)
                if number:
                    return number
            node_text = node.get_text(' ', strip=True)
            for pattern in STOCK_PATTERNS:
                found = re.search(pattern, node_text, flags=re.I)
                if found:
                    return _digits(found.group(1))

    full_text = f'{html or ""} {text or ""}'
    for pattern in STOCK_PATTERNS:
        found = re.search(pattern, full_text, flags=re.I)
        if found:
            return _digits(found.group(1))
    return ''


def detect_stock_status(html: str, text: str = '') -> str:
    full = normalize_key(f'{html or ""} {text or ""}')
    if any(normalize_key(term) in full for term in OUT_STOCK_TERMS):
        return '0'
    return ''


def detect_real_stock(html: str, text: str = '') -> str:
    """Tenta detectar estoque real sem depender do mapeamento.

    Ordem proposital:
    1. JSON/scripts e variáveis com quantidade.
    2. DOM com atributos de estoque.
    3. Texto visível com padrões de quantidade.
    4. Status sem estoque = 0.

    Simulação completa de carrinho depende de endpoint específico por loja. Este módulo
    deixa a base isolada para evoluir por site sem contaminar o crawler geral.
    """
    value = detect_stock_from_json(html)
    if value:
        return value
    value = detect_stock_from_dom(html, text)
    if value:
        return value
    return detect_stock_status(html, text)
