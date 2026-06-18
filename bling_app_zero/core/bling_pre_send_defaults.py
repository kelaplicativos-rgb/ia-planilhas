from __future__ import annotations

import re
from typing import Any, Mapping
from urllib.parse import urlparse

import pandas as pd

from bling_app_zero.engines.brand_title_detector import detect_brand_from_title

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_pre_send_defaults.py'
DEFAULT_BRAND = 'Genérico'
DEFAULT_CONDITION = 'Novo'
DEFAULT_PRODUCTION = 'Terceiros'
DEFAULT_UNIT = 'UN'
DEFAULT_MEASURE_UNIT = 'Centímetros'
DEFAULT_DEPARTMENT = 'Adulto Unissex'

_NAME_FIELDS = ('nome', 'Nome', 'produto', 'Produto', 'titulo', 'Título', 'título', 'descricao produto', 'Descrição produto', 'descricao_produto')
_DESC_FIELDS = ('descricao', 'Descrição', 'descrição', 'descricao_curta', 'Descrição Curta', 'descrição curta', 'detalhes', 'Detalhes')
_CODE_FIELDS = ('codigo', 'Código', 'código', 'sku', 'SKU', 'codigo produto', 'Código produto', 'código produto')
_GTIN_FIELDS = ('gtin', 'GTIN', 'ean', 'EAN', 'GTIN/EAN', 'gtin/ean', 'codigo de barras', 'Código de barras', 'código de barras')
_BRAND_FIELDS = ('marca', 'Marca', 'fabricante', 'Fabricante')
_CONDITION_FIELDS = ('condicao', 'condição', 'Condição', 'Condicao', 'condicao_produto', 'condição_produto', 'estado', 'Estado')
_PRODUCTION_FIELDS = ('producao', 'produção', 'Produção', 'Producao', 'tipo_producao', 'tipo produção')
_UNIT_FIELDS = ('unidade', 'Unidade')
_MEASURE_UNIT_FIELDS = ('unidade de medida', 'Unidade de medida', 'unidade das medidas', 'Unidade das medidas', 'unidade medida', 'Unidade medida', 'unidade_medida')
_LINK_FIELDS = ('linkExterno', 'link externo', 'Link Externo', 'url produto', 'URL produto', 'link produto', 'Link produto', 'produto_url', 'source_url', 'url_origem', 'link_origem')
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
_IMAGE_URL_MARKERS = (
    '/storage/', 'product_images', 'product-images', '/images/', '/image/', '/img/', '/fotos/', '/foto/',
    'supabase.co/storage', 'cdn.', 'cloudinary.', 'googleusercontent.com', 'fbcdn.', 'static.', 'assets.',
)
_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.svg', '.avif')
_PRODUCT_PATH_MARKERS = ('/produto/', '/produtos/', '/product/', '/products/', '/p/', '/item/', '/itens/')


def _clean(value: object) -> str:
    text = str(value or '').strip()
    if text.lower() in {'nan', 'none', 'null'}:
        return ''
    return ' '.join(text.split())


def _digits(value: object) -> str:
    return re.sub(r'\D+', '', str(value or ''))


def _valid_gtin(value: object) -> str:
    digits = _digits(value)
    return digits if len(digits) in {8, 12, 13, 14} else ''


def _looks_like_image_or_storage_url(url: object) -> bool:
    text = _clean(url).lower()
    if not text.startswith(('http://', 'https://')):
        return False
    parsed = urlparse(text)
    path = parsed.path.lower()
    return any(marker in text for marker in _IMAGE_URL_MARKERS) or path.endswith(_IMAGE_EXTENSIONS)


def _is_real_product_url(url: object) -> bool:
    text = _clean(url)
    if not text.startswith(('http://', 'https://')):
        return False
    if _looks_like_image_or_storage_url(text):
        return False
    parsed = urlparse(text)
    path = parsed.path.lower()
    return bool(parsed.netloc) and any(marker in path for marker in _PRODUCT_PATH_MARKERS)


def _valid_product_url(value: object) -> str:
    text = _clean(value)
    return text if _is_real_product_url(text) else ''


def _norm_brand(value: str) -> str:
    return re.sub(r'\s+', ' ', str(value or '').replace('’', "'").strip()).strip(' -_/|.,;:')


def _brand_key(value: str) -> str:
    return re.sub(r'[^a-z0-9]+', ' ', _norm_brand(value).lower()).strip()


def _brand_is_valid(value: str, title_context: str = '') -> bool:
    brand = _norm_brand(value)
    if not brand:
        return False
    low = brand.lower()
    if low in _STORE_BRANDS or any(low.startswith(item) for item in _STORE_BRANDS):
        return False
    if len(brand) < 2 or len(brand) > 40:
        return False

    detected = _norm_brand(detect_brand_from_title(title_context or '', fallback=brand))
    if not detected:
        return False
    if not title_context:
        return True
    return _brand_key(detected) == _brand_key(brand)


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


def _first_real_product_url(data: Mapping[str, Any]) -> str:
    lowered = {str(k).lower(): k for k in data.keys()}
    for field in _LINK_FIELDS:
        key = field if field in data else lowered.get(field.lower())
        if key is None:
            continue
        value = _valid_product_url(data.get(key))
        if value:
            return value
    for key, value in data.items():
        normalized_key = str(key or '').lower()
        if any(marker in normalized_key for marker in ('imagem', 'image', 'foto', 'picture', 'thumbnail')):
            continue
        value = _valid_product_url(value)
        if value:
            return value
    return ''


def infer_brand_from_title(title: str) -> str:
    return _norm_brand(detect_brand_from_title(title))


def apply_product_send_defaults(row: Any) -> dict[str, Any]:
    try:
        data = dict(row.to_dict()) if hasattr(row, 'to_dict') else dict(row or {})
    except Exception:
        return row

    nome = _first(data, _NAME_FIELDS)
    descricao = _first(data, _DESC_FIELDS)
    codigo = _first(data, _CODE_FIELDS)
    marca = _first(data, _BRAND_FIELDS)
    gtin = _valid_gtin(_first(data, _GTIN_FIELDS) or codigo)
    link_externo = _first_real_product_url(data)

    if not nome:
        fallback = descricao or codigo
        if fallback:
            key = _target_key(data, 'nome', _NAME_FIELDS)
            data[key] = fallback[:120]
            nome = fallback[:120]

    if not descricao and nome:
        key = _target_key(data, 'descricao', _DESC_FIELDS)
        data[key] = nome

    brand_context = nome or descricao
    if not _brand_is_valid(marca, title_context=brand_context):
        inferred = infer_brand_from_title(brand_context)
        key = _target_key(data, 'marca', _BRAND_FIELDS)
        data[key] = inferred if _brand_is_valid(inferred, title_context=brand_context) else DEFAULT_BRAND

    data[_target_key(data, 'condicao', _CONDITION_FIELDS)] = DEFAULT_CONDITION
    data[_target_key(data, 'producao', _PRODUCTION_FIELDS)] = DEFAULT_PRODUCTION
    data[_target_key(data, 'unidade', _UNIT_FIELDS)] = DEFAULT_UNIT
    data[_target_key(data, 'unidade de medida', _MEASURE_UNIT_FIELDS)] = DEFAULT_MEASURE_UNIT

    if not _first(data, _DEPARTMENT_FIELDS):
        data[_target_key(data, 'departamento', _DEPARTMENT_FIELDS)] = DEFAULT_DEPARTMENT

    tax_key = _target_key(data, 'gtinTributario', _TAX_GTIN_FIELDS)
    data[tax_key] = gtin
    for field in _GTIN_FIELDS:
        key = _target_key(data, field, (field,))
        if key in data and _digits(data.get(key)) and not gtin:
            data[key] = ''

    link_key = _target_key(data, 'linkExterno', _LINK_FIELDS)
    data[link_key] = link_externo

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
    'DEFAULT_MEASURE_UNIT',
    'DEFAULT_DEPARTMENT',
    'apply_dataframe_send_defaults',
    'apply_product_send_defaults',
    'infer_brand_from_title',
]
