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

MODEL_HINT_WORDS = {
    'modelo', 'model', 'mod', 'ref', 'referencia', 'referência', 'codigo', 'código', 'cod', 'sku',
    'part', 'pn', 'mpn', 'serial', 'serie', 'série', 'linha', 'versao', 'versão', 'cor', 'tamanho',
    'voltagem', 'volts', 'w', 'mah', 'gb', 'tb', 'mm', 'cm', 'pol', 'polegadas',
}

BRAND_PREFIX_RE = re.compile(
    r'\b(?:marca|brand|fabricante|manufacturer)\s*[:=\-]\s*([A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9 .&’\'-]{1,40})',
    re.IGNORECASE,
)


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


def _looks_like_model_or_code(value: str) -> bool:
    text = clean_cell(value or '')
    key = normalize_key(text)
    if not key:
        return True
    if key in GENERIC_WORDS or key in MODEL_HINT_WORDS:
        return True
    if any(part in MODEL_HINT_WORDS for part in key.split()):
        return True
    if re.search(r'\d', key):
        return True
    if re.search(r'\b(?:[a-z]{1,4}\d+[a-z0-9]*|\d+[a-z]{1,4})\b', key):
        return True
    if re.search(r'[/-]', text) and len(_tokens(text)) <= 3:
        return True
    if len(key) <= 2:
        return True
    return False


def _is_trusted_brand_value(value: str) -> bool:
    text = clean_cell(value or '')
    key = normalize_key(text)
    if not key:
        return False
    if key in {normalize_key(brand) for brand in KNOWN_BRANDS}:
        return True
    if key in BRAND_ALIASES:
        return True
    if _looks_like_model_or_code(text):
        return False
    words = key.split()
    if len(words) > 3:
        return False
    if any(word in GENERIC_WORDS or word in MODEL_HINT_WORDS for word in words):
        return False
    return bool(re.fullmatch(r'[a-z0-9]+(?: [a-z0-9]+){0,2}', key))


def _clean_brand(value: str) -> str:
    text = clean_cell(value or '').replace("'", '’')
    return BRAND_ALIASES.get(normalize_key(text), text)


def _known_brand_from_text(text: str) -> str:
    normalized_text = normalize_key(text)
    if not normalized_text:
        return ''

    for alias, brand in BRAND_ALIASES.items():
        alias_key = normalize_key(alias)
        if re.search(rf'(^|\s){re.escape(alias_key)}(\s|$)', normalized_text):
            return brand

    for brand in KNOWN_BRANDS:
        brand_key = normalize_key(brand)
        if brand_key and re.search(rf'(^|\s){re.escape(brand_key)}(\s|$)', normalized_text):
            return _clean_brand(brand)

    return ''


def detect_brand_from_title(title: str, fallback: str = '') -> str:
    text = clean_cell(title or '')
    fallback_clean = _clean_brand(fallback or '')

    explicit = BRAND_PREFIX_RE.search(text)
    if explicit:
        explicit_brand = _clean_brand(explicit.group(1))
        if _is_trusted_brand_value(explicit_brand):
            return explicit_brand

    detected = _known_brand_from_text(text)
    if detected:
        return detected

    if fallback_clean and _is_trusted_brand_value(fallback_clean):
        return fallback_clean

    return ''