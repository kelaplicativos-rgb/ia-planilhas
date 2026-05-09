from __future__ import annotations

import re

from bling_app_zero.core.text import clean_cell, normalize_key

KNOWN_BRANDS = [
    'H’maston', 'H\'maston', 'Hmaston', 'Multilaser', 'Intelbras', 'Elgin', 'Xiaomi', 'Samsung',
    'Apple', 'Motorola', 'LG', 'Sony', 'JBL', 'Lenovo', 'Dell', 'HP', 'Acer', 'Asus', 'TP-Link',
    'D-Link', 'Mercusys', 'Logitech', 'Redragon', 'Knup', 'Exbom', 'Tomate', 'Inova', 'KAP', 'Kapbom',
    'Aquario', 'Aquário', 'Geonav', 'I2GO', 'Elg', 'Viniks', 'Fortrek', 'C3Tech', 'Hayom', 'Kimaster',
    'Sumay', 'Kaidi', 'Baseus', 'Ugreen', 'Awei', 'B-Max', 'Jeway', 'Gshield', 'Mox', 'Kross', 'Bright',
    'Leadership', 'Goldentec', 'Oex', 'Maxprint', 'Lehmox', 'Dazz', 'Multikids', 'Tedge', 'Vinik',
]

BRAND_ALIASES = {
    'h maston': 'H’maston',
    'h’maston': 'H’maston',
    "h'maston": 'H’maston',
    'hmaston': 'H’maston',
    'h m aston': 'H’maston',
    'kap 2u': 'KAP',
    'kap': 'KAP',
    'c3 tech': 'C3Tech',
    'tp link': 'TP-Link',
    'd link': 'D-Link',
    'aquario': 'Aquário',
}

GENERIC_WORDS = {
    'produto', 'controle', 'carregador', 'cabo', 'fone', 'mouse', 'teclado', 'caixa', 'som', 'pen',
    'drive', 'adaptador', 'suporte', 'camera', 'câmera', 'pelicula', 'película', 'capinha', 'fonte',
    'usb', 'tipo', 'type', 'sem', 'fio', 'recarregavel', 'recarregável', 'completo', 'micro', 'gamer',
    'para', 'com', 'sem', 'novo', 'original', 'premium', 'universal', 'digital', 'wireless', 'bluetooth',
}


def _tokens(title: str) -> list[str]:
    return [token for token in re.split(r'[^A-Za-zÀ-ÿ0-9]+', title or '') if token]


def _is_generic_token(token: str) -> bool:
    key = normalize_key(token)
    if not key or key in GENERIC_WORDS:
        return True
    if key.isdigit():
        return True
    if re.fullmatch(r'[a-z]?\d+[a-z0-9]*', key):
        return True
    return False


def _clean_brand(value: str) -> str:
    text = clean_cell(value or '').replace("'", '’')
    return BRAND_ALIASES.get(normalize_key(text), text)


def detect_brand_from_title(title: str, fallback: str = '') -> str:
    text = clean_cell(title or '')
    fallback_clean = _clean_brand(fallback or '')
    if not text:
        return fallback_clean

    normalized_title = normalize_key(text)

    for alias, brand in BRAND_ALIASES.items():
        if normalize_key(alias) in normalized_title:
            return brand

    for brand in KNOWN_BRANDS:
        brand_key = normalize_key(brand)
        if not brand_key:
            continue
        if re.search(rf'(^|\s){re.escape(brand_key)}(\s|$)', normalized_title):
            return _clean_brand(brand)

    if fallback_clean and not _is_generic_token(fallback_clean):
        return fallback_clean

    tokens = _tokens(text)
    for token in tokens:
        key = normalize_key(token)
        if len(key) < 3 or _is_generic_token(token):
            continue
        if token.isupper() and len(token) >= 3:
            return _clean_brand(token)

    for token in reversed(tokens):
        key = normalize_key(token)
        if len(key) >= 4 and not _is_generic_token(token):
            return _clean_brand(token)

    return fallback_clean
