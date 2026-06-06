from __future__ import annotations

import re
from typing import Any, Mapping

import pandas as pd

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_pre_send_defaults.py'
DEFAULT_BRAND = 'Genérico'

_NAME_FIELDS = ('nome', 'Nome', 'produto', 'Produto', 'titulo', 'Título', 'título', 'descricao produto', 'Descrição produto', 'descricao_produto')
_DESC_FIELDS = ('descricao', 'Descrição', 'descrição', 'descricao_curta', 'Descrição Curta', 'descrição curta', 'detalhes', 'Detalhes')
_CODE_FIELDS = ('codigo', 'Código', 'código', 'sku', 'SKU', 'gtin', 'GTIN', 'ean', 'EAN')
_BRAND_FIELDS = ('marca', 'Marca', 'fabricante', 'Fabricante')
_STORE_BRANDS = {'mega center', 'mega center eletronicos', 'mega center eletrônicos', 'stoqui', 'stoqui shop'}
_STOPWORDS = {
    'fone', 'ouvido', 'estereo', 'estéreo', 'sem', 'fio', 'bluetooth', 'bt', 'power', 'bank', 'carregador', 'cabo',
    'adaptador', 'teclado', 'mouse', 'caixa', 'som', 'suporte', 'pelicula', 'película', 'controle', 'lampada', 'lâmpada',
    'smart', 'relogio', 'relógio', 'infantil', 'adulto', 'original', 'usb', 'tipo', 'para', 'com', 'preto', 'branco',
    'azul', 'rosa', 'vermelho', 'verde', 'cinza', 'dourado', 'prata', 'mini', 'micro', 'novo', 'produto', 'wireless',
}
_KNOWN_BRANDS = (
    'H\'MASTON', 'HMASTON', 'KAIDI', 'KNUP', 'KAPBOM', 'INOVA', 'ALTOMEX', 'LEHMOX', 'IT-BLUE',
    'ITBLUE', 'X-CELL', 'XCELL', 'SUMEXR', 'EXBOM', 'JBL', 'SAMSUNG', 'MOTOROLA', 'XIAOMI', 'APPLE', 'LENOVO',
    'MULTILASER', 'POSITIVO', 'INTELBRAS', 'ELGIN', 'BRITANIA', 'MONDIAL', 'PHILCO', 'GEONAV', 'BASEUS', 'BOROFONE',
    'HOCO', 'AWEI', 'TREQA', 'REMAX', 'ORICO', 'UGREEN', 'LDNIO', 'MCDODO', 'XO', 'KZ', 'EDIFIER', 'LOGITECH',
)


def _clean(value: object) -> str:
    text = str(value or '').strip()
    if text.lower() in {'nan', 'none', 'null'}:
        return ''
    return ' '.join(text.split())


def _norm_brand(value: str) -> str:
    return re.sub(r'\s+', ' ', str(value or '').replace('’', "'").strip()).strip(' -_/|.,;:')


def _brand_is_valid(value: str) -> bool:
    brand = _norm_brand(value)
    if not brand:
        return False
    low = brand.lower()
    if low in _STORE_BRANDS or any(low.startswith(item) for item in _STORE_BRANDS):
        return False
    if low in _STOPWORDS:
        return False
    if len(brand) < 2 or len(brand) > 40:
        return False
    return True


def _first(data: Mapping[str, Any], fields: tuple[str, ...]) -> str:
    lowered = {str(k).lower(): k for k in data.keys()}
    for field in fields:
        if field in data:
            value = _clean(data.get(field))
            if value:
                return value
        key = lowered.get(field.lower())
        if key is not None:
            value = _clean(data.get(key))
            if value:
                return value
    return ''


def _target_key(data: Mapping[str, Any], preferred: str, aliases: tuple[str, ...]) -> str:
    lowered = {str(k).lower(): str(k) for k in data.keys()}
    for alias in aliases:
        key = lowered.get(alias.lower())
        if key:
            return key
    return preferred


def infer_brand_from_title(title: str) -> str:
    text = _clean(title).replace('’', "'")
    if not text:
        return ''
    upper_text = text.upper()
    for brand in _KNOWN_BRANDS:
        pattern = r'(?<![A-Z0-9])' + re.escape(brand.upper()) + r'(?![A-Z0-9])'
        if re.search(pattern, upper_text):
            if brand.upper() in {'H\'MASTON', 'HMASTON'}:
                return "H'maston"
            return _norm_brand(brand.title() if brand.isupper() and len(brand) > 3 else brand)

    patterns = [
        r'\bmarca\s+([A-Za-z0-9\'\-]{2,30})\b',
        r'\bmodelo\s+([A-Za-z]{2,30})\b',
        r'[-|/]\s*([A-Za-z][A-Za-z0-9\'\-]{2,30})\b',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            candidate = _norm_brand(match.group(1))
            if _brand_is_valid(candidate):
                return candidate

    tokens = re.findall(r"[A-Za-z][A-Za-z0-9'\-]{2,30}", text)
    for token in tokens:
        candidate = _norm_brand(token)
        if not _brand_is_valid(candidate):
            continue
        low = candidate.lower()
        if low in _STOPWORDS:
            continue
        if candidate.isupper() or "'" in candidate or '-' in candidate:
            return candidate
    return ''


def apply_product_send_defaults(row: Any) -> dict[str, Any]:
    try:
        data = dict(row.to_dict()) if hasattr(row, 'to_dict') else dict(row or {})
    except Exception:
        return row

    nome = _first(data, _NAME_FIELDS)
    descricao = _first(data, _DESC_FIELDS)
    codigo = _first(data, _CODE_FIELDS)
    marca = _first(data, _BRAND_FIELDS)

    if not nome:
        fallback = descricao or codigo
        if fallback:
            key = _target_key(data, 'nome', _NAME_FIELDS)
            data[key] = fallback[:120]
            nome = fallback[:120]

    if not descricao and nome:
        key = _target_key(data, 'descricao', _DESC_FIELDS)
        data[key] = nome

    if not _brand_is_valid(marca):
        inferred = infer_brand_from_title(nome or descricao)
        key = _target_key(data, 'marca', _BRAND_FIELDS)
        data[key] = inferred if _brand_is_valid(inferred) else DEFAULT_BRAND

    return data


def _ordered_columns(original_columns: list[str], rows: list[dict[str, Any]]) -> list[str]:
    out = list(original_columns)
    seen = {str(column) for column in out}
    for row in rows:
        for key in row.keys():
            text_key = str(key)
            if text_key not in seen:
                out.append(text_key)
                seen.add(text_key)
    return out


def apply_dataframe_send_defaults(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    rows = [apply_product_send_defaults(row) for _idx, row in df.fillna('').iterrows()]
    if not rows:
        return df
    columns = _ordered_columns(list(df.columns), rows)
    return pd.DataFrame(rows, columns=columns).fillna('')


__all__ = ['RESPONSIBLE_FILE', 'DEFAULT_BRAND', 'apply_dataframe_send_defaults', 'apply_product_send_defaults', 'infer_brand_from_title']
