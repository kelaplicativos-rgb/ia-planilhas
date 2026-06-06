from __future__ import annotations

import re
from typing import Any, Mapping

import pandas as pd

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_pre_send_defaults.py'
DEFAULT_BRAND = 'Genérico'
DEFAULT_CONDITION = 'Novo'
DEFAULT_PRODUCTION = 'Terceiros'
DEFAULT_UNIT = 'Centímetros'
DEFAULT_DEPARTMENT = 'Adulto Unissex'

_NAME_FIELDS = ('nome', 'Nome', 'produto', 'Produto', 'titulo', 'Título', 'título', 'descricao produto', 'Descrição produto', 'descricao_produto')
_DESC_FIELDS = ('descricao', 'Descrição', 'descrição', 'descricao_curta', 'Descrição Curta', 'descrição curta', 'detalhes', 'Detalhes')
_CODE_FIELDS = ('codigo', 'Código', 'código', 'sku', 'SKU', 'gtin', 'GTIN', 'ean', 'EAN')
_BRAND_FIELDS = ('marca', 'Marca', 'fabricante', 'Fabricante')
_CONDITION_FIELDS = ('condicao', 'condição', 'Condição', 'Condicao', 'condicao_produto', 'condição_produto', 'estado', 'Estado')
_PRODUCTION_FIELDS = ('producao', 'produção', 'Produção', 'Producao', 'tipo_producao', 'tipo produção')
_UNIT_FIELDS = ('unidade', 'Unidade', 'unidade de medida', 'Unidade de medida', 'unidade_medida')
_LINK_FIELDS = ('linkExterno', 'link externo', 'Link Externo', 'url', 'URL', 'link', 'Link', 'url produto', 'URL produto', 'link produto', 'Link produto', 'produto_url', 'source_url')
_TAX_GTIN_FIELDS = ('gtinTributario', 'gtin tributário', 'GTIN/EAN tributário', 'gtin/ean tributário', 'eanTributario', 'ean tributário')
_DEPARTMENT_FIELDS = ('departamento', 'Departamento')
_COMPLEMENT_FIELDS = ('descricaoComplementar', 'descrição complementar', 'descricao complementar', 'Descrição complementar', 'complementar')
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


def _digits(value: object) -> str:
    return re.sub(r'\D+', '', str(value or ''))


def _valid_url(value: object) -> str:
    text = _clean(value)
    return text if text.startswith(('http://', 'https://')) else ''


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
    condicao = _first(data, _CONDITION_FIELDS)
    producao = _first(data, _PRODUCTION_FIELDS)
    unidade = _first(data, _UNIT_FIELDS)
    departamento = _first(data, _DEPARTMENT_FIELDS)
    link_externo = _first(data, _LINK_FIELDS)
    gtin = _digits(_first(data, _CODE_FIELDS))
    gtin_tributario = _digits(_first(data, _TAX_GTIN_FIELDS))

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

    if not condicao:
        data[_target_key(data, 'condicao', _CONDITION_FIELDS)] = DEFAULT_CONDITION
    if not producao:
        data[_target_key(data, 'producao', _PRODUCTION_FIELDS)] = DEFAULT_PRODUCTION
    if not unidade:
        data[_target_key(data, 'unidade', _UNIT_FIELDS)] = DEFAULT_UNIT
    if not departamento:
        data[_target_key(data, 'departamento', _DEPARTMENT_FIELDS)] = DEFAULT_DEPARTMENT
    if not gtin_tributario and len(gtin) in {8, 12, 13, 14}:
        data[_target_key(data, 'gtinTributario', _TAX_GTIN_FIELDS)] = gtin
    if _valid_url(link_externo):
        data[_target_key(data, 'linkExterno', _LINK_FIELDS)] = link_externo

    # Regra fixa solicitada: descrição complementar sempre limpa/vazia.
    data[_target_key(data, 'descricaoComplementar', _COMPLEMENT_FIELDS)] = ''

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


__all__ = [
    'RESPONSIBLE_FILE',
    'DEFAULT_BRAND',
    'DEFAULT_CONDITION',
    'DEFAULT_PRODUCTION',
    'DEFAULT_UNIT',
    'DEFAULT_DEPARTMENT',
    'apply_dataframe_send_defaults',
    'apply_product_send_defaults',
    'infer_brand_from_title',
]
