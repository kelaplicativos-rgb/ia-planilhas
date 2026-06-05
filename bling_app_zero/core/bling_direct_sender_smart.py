from __future__ import annotations

import re
from typing import Any, Callable, Iterable

import pandas as pd
import requests
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_direct_sender import DirectSendResult
from bling_app_zero.core.bling_direct_sender_safe import (
    is_direct_send_available,
    preview_payloads as _safe_preview_payloads,
    send_dataframe_to_bling as _safe_send_dataframe_to_bling,
)
from bling_app_zero.core.bling_smart_enrichment import enrich_product_payload_fields
from bling_app_zero.core.bling_token_store import load_token
from bling_app_zero.core.operation_contract import OP_CADASTRO, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_direct_sender_smart.py'
DEFAULT_API_BASE_URL = 'https://www.bling.com.br/Api/v3'
SEND_TIMEOUT = 30
LOOKUP_TIMEOUT = 15
CATEGORY_TIMEOUT = 15
CATEGORY_CACHE_KEY = 'bling_smart_sender_category_cache_v3'
PRODUCT_CACHE_KEY = 'bling_smart_sender_product_cache_v3'

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    'codigo': ('código', 'codigo', 'sku', 'ref', 'referencia', 'referência', 'codigo produto', 'código produto', 'cod produto', 'cod', 'id produto', 'id do produto'),
    'nome': ('nome', 'produto', 'título', 'titulo', 'nome produto', 'nome do produto', 'descrição produto', 'descricao produto'),
    'descricao': ('descrição', 'descricao', 'descrição do produto', 'descricao do produto', 'detalhes'),
    'descricao_curta': ('descrição curta', 'descricao curta', 'descrição resumida', 'descricao resumida', 'resumo', 'sinopse'),
    'descricao_complementar': ('descricao complementar', 'descrição complementar', 'complementar', 'descrição detalhada', 'descricao detalhada', 'ficha tecnica', 'ficha técnica', 'caracteristicas', 'características', 'informações adicionais', 'informacoes adicionais'),
    'preco': ('preço', 'preco', 'preço unitário', 'preco unitario', 'preço unitário (obrigatório)', 'preco unitario (obrigatorio)', 'valor', 'valor venda', 'preço de venda', 'preco de venda'),
    'gtin': ('gtin', 'ean', 'codigo de barras', 'código de barras', 'gtin/ean'),
    'marca': ('marca', 'fabricante'),
    'unidade': ('unidade', 'un'),
    'ncm': ('ncm',),
    'cest': ('cest',),
    'origem': ('origem', 'origem produto', 'origem do produto'),
    'categoria': ('categoria', 'categoria produto', 'categoria do produto', 'departamento', 'grupo'),
    'imagens': ('imagens', 'imagem', 'url imagem', 'url imagens', 'fotos', 'foto'),
    'peso_liquido': ('peso liquido', 'peso líquido', 'peso_liquido', 'peso líquido kg', 'peso liquido kg'),
    'peso_bruto': ('peso bruto', 'peso_bruto', 'peso bruto kg'),
    'largura': ('largura', 'largura cm'),
    'altura': ('altura', 'altura cm'),
    'profundidade': ('profundidade', 'comprimento', 'profundidade cm', 'comprimento cm'),
}

KNOWN_BRANDS: tuple[str, ...] = (
    'Samsung', 'Apple', 'Motorola', 'Xiaomi', 'LG', 'JBL', 'Sony', 'Philips', 'Epson', 'Canon', 'HP', 'Dell', 'Lenovo',
    'Logitech', 'Redragon', 'Intelbras', 'Positivo', 'Multilaser', 'Elgin', 'Exbom', 'Knup', 'Inova', "H'Maston",
    'H Maston', 'It-Blue', 'Altomex', 'Goldentec', 'Hoopson', 'Hayom', 'Aiwa', 'Tomate', 'Sumay', 'Aquario', 'Aquário',
    'Bright', 'Leadership', 'Maxprint', 'C3Tech', 'Fortrek', 'Dazz', 'OEX', 'Baseus', 'Hoco', 'Lenoxx', 'Mondial',
    'Britania', 'Britânia', 'Philco', 'Acer', 'Asus', 'Kingston', 'Sandisk', 'Seagate', 'Western Digital', 'WD', 'TP-Link',
    'D-Link', 'Mercusys', 'Tenda', 'Intel', 'AMD', 'Nvidia', 'Microsoft', 'Google', 'Amazon', 'Xtrad', 'Kross', 'Gshield',
    'Kaidi', 'KD', 'Kapbom', 'Kimaster', 'Kemei', 'Lelong', 'X-Cell', 'Mox', 'G-Tech', 'Jeway', 'Deko', 'Deko Eletrônicos',
)
BLOCKED_BRAND_TERMS = ('mega center', 'megacenter', 'stoqui', 'loja', 'eletronicos', 'eletrônicos')


def _secret(name: str, default: str = '') -> str:
    try:
        bling = st.secrets.get('bling', {})
        value = bling.get(name, default) if hasattr(bling, 'get') else default
        return str(value or default).strip()
    except Exception:
        return default


def _api_base_url() -> str:
    return (_secret('api_base_url', DEFAULT_API_BASE_URL) or DEFAULT_API_BASE_URL).rstrip('/')


def _url(path: str) -> str:
    if str(path or '').startswith(('http://', 'https://')):
        return str(path)
    return _api_base_url() + '/' + str(path or '').lstrip('/')


def _headers(token: dict[str, Any]) -> dict[str, str]:
    return {'Accept': 'application/json', 'Content-Type': 'application/json', 'Authorization': f"Bearer {token.get('access_token')}"}


def _normalize_column_name(value: object) -> str:
    text = str(value or '').strip().lower()
    text = text.replace('ã', 'a').replace('á', 'a').replace('à', 'a').replace('â', 'a')
    text = text.replace('é', 'e').replace('ê', 'e').replace('í', 'i')
    text = text.replace('ó', 'o').replace('ô', 'o').replace('õ', 'o')
    text = text.replace('ú', 'u').replace('ç', 'c')
    text = re.sub(r'[^a-z0-9]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def _column_map(columns: Iterable[object]) -> dict[str, str]:
    normalized = {_normalize_column_name(column): str(column) for column in columns}
    out: dict[str, str] = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            column = normalized.get(_normalize_column_name(alias))
            if column:
                out[field] = column
                break
    return out


def _value(row: pd.Series, mapping: dict[str, str], field: str) -> str:
    column = mapping.get(field)
    if not column:
        return ''
    value = row.get(column, '')
    if pd.isna(value):
        return ''
    return str(value or '').strip()


def _number_value(value: object) -> float | None:
    text = str(value or '').strip().replace('R$', '').replace('\xa0', '').replace(' ', '')
    if not text:
        return None
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    else:
        text = text.replace(',', '.')
    text = re.sub(r'[^0-9.\-]+', '', text)
    try:
        return float(text) if text not in {'', '-', '.', '-.'} else None
    except Exception:
        return None


def _api_number(value: float) -> int | float:
    number = float(value)
    return int(number) if number.is_integer() else round(number, 4)


def _digits_only(value: object) -> str:
    return re.sub(r'\D+', '', str(value or ''))


def _clean_text(value: object, limit: int = 120) -> str:
    text = str(value or '').replace('\u200b', '').replace('\ufeff', '').strip()
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:limit]


def _sanitize_code(value: object, *, fallback: object = '') -> str:
    raw = str(value or '').strip() or str(fallback or '').strip()
    if not raw:
        return ''
    if raw.lower().startswith(('http://', 'https://')):
        raw = raw.rstrip('/').rsplit('/', 1)[-1]
    raw = raw.replace('@', '-')
    raw = re.sub(r'[^A-Za-z0-9._-]+', '-', raw).strip('-._')
    digits = _digits_only(raw)
    if len(digits) in {8, 12, 13, 14}:
        return digits
    return raw[:60]


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in payload.items():
        if value in ('', None, {}, []):
            continue
        if isinstance(value, dict):
            nested = _clean_payload(value)
            if nested:
                clean[key] = nested
            continue
        if isinstance(value, list):
            items = [item for item in value if item not in ('', None, {}, [])]
            if items:
                clean[key] = items
            continue
        clean[key] = value
    return clean


def _cadastro_schema_error(df: pd.DataFrame) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return 'Cadastro bloqueado: não há produtos para enviar.'
    mapping = _column_map(df.columns)
    normalized_columns = {_normalize_column_name(column) for column in df.columns}
    stock_only_columns = {'quantidade', 'id', 'codigo', 'gtin', 'deposito'}
    content_fields = {'nome', 'descricao', 'descricao_curta', 'descricao_complementar'}
    has_name_or_description = any(mapping.get(field) for field in content_fields)
    has_price = bool(mapping.get('preco'))
    has_stock_shape = normalized_columns.issubset(stock_only_columns) and {'quantidade', 'deposito'}.intersection(normalized_columns)
    if has_stock_shape or not has_name_or_description or not has_price:
        add_audit_event('bling_smart_cadastro_schema_blocked', area='BLING_ENVIO', status='BLOQUEADO', details={'columns': list(map(str, df.columns)), 'mapped_fields': sorted(mapping.keys()), 'has_stock_shape': bool(has_stock_shape), 'has_name_or_description': has_name_or_description, 'has_price': has_price, 'responsible_file': RESPONSIBLE_FILE})
        return 'Cadastro bloqueado por segurança: a tabela preparada não parece ser cadastro de produtos. Ela está sem Nome/Descrição e/ou Preço, ou está com formato de estoque. Refaça o preview final antes de enviar ao Bling.'
    price_column = mapping.get('preco', '')
    positive_prices = 0
    if price_column:
        for value in df[price_column].head(80).tolist():
            price = _number_value(value)
            if price is not None and price > 0:
                positive_prices += 1
    if positive_prices == 0:
        add_audit_event('bling_smart_cadastro_price_blocked', area='BLING_ENVIO', status='BLOQUEADO', details={'columns': list(map(str, df.columns)), 'price_column': price_column, 'responsible_file': RESPONSIBLE_FILE})
        return 'Cadastro bloqueado por segurança: nenhum preço positivo foi encontrado. O Bling não deve receber produtos com preço zerado.'
    return ''


def _extract_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ('data', 'dados', 'items', 'result', 'results'):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_items(value)
            if nested:
                return nested
    return []


def _product_cache() -> dict[str, str]:
    cache = st.session_state.get(PRODUCT_CACHE_KEY)
    if not isinstance(cache, dict):
        cache = {}
        st.session_state[PRODUCT_CACHE_KEY] = cache
    return cache


def _category_cache() -> dict[str, str]:
    cache = st.session_state.get(CATEGORY_CACHE_KEY)
    if not isinstance(cache, dict):
        cache = {}
        st.session_state[CATEGORY_CACHE_KEY] = cache
    return cache


def _item_id(item: dict[str, Any]) -> str:
    return str(item.get('id') or item.get('idProduto') or '').strip()


def _item_identifiers(item: dict[str, Any]) -> list[str]:
    tributacao = item.get('tributacao') if isinstance(item.get('tributacao'), dict) else {}
    return [str(v or '').strip() for v in (item.get('codigo'), item.get('sku'), item.get('gtin'), item.get('ean'), item.get('codigoBarras'), tributacao.get('gtin'), tributacao.get('ean')) if str(v or '').strip()]


def _resolve_product_id(token: dict[str, Any], candidates: Iterable[object]) -> str:
    headers = _headers(token)
    cache = _product_cache()
    lookup_path = _secret('product_lookup_path', '/produtos') or '/produtos'
    for candidate in candidates:
        value = _sanitize_code(candidate)
        if not value:
            continue
        key = value.lower()
        if key in cache:
            return str(cache.get(key) or '')
        for params in ({'codigo': value}, {'criterio': value}, {'pesquisa': value}):
            try:
                response = requests.get(_url(lookup_path), headers=headers, params=params, timeout=LOOKUP_TIMEOUT)
                if response.status_code >= 400:
                    continue
                items = _extract_items(response.json())
                exact: list[str] = []
                loose: list[str] = []
                for item in items:
                    item_id = _item_id(item)
                    if not item_id:
                        continue
                    identifiers = [identifier.lower() for identifier in _item_identifiers(item)]
                    if key in identifiers:
                        exact.append(item_id)
                    elif len(items) == 1:
                        loose.append(item_id)
                product_id = exact[0] if exact else (loose[0] if loose else '')
                if product_id:
                    cache[key] = product_id
                    add_audit_event('bling_smart_product_resolved_for_upsert', area='BLING_ENVIO', status='OK', details={'candidate': value, 'product_id': product_id, 'params': params, 'responsible_file': RESPONSIBLE_FILE})
                    return product_id
            except Exception as exc:
                add_audit_event('bling_smart_product_lookup_exception', area='BLING_ENVIO', status='AVISO', details={'candidate': value, 'error': str(exc)[:180], 'responsible_file': RESPONSIBLE_FILE})
        cache[key] = ''
    return ''


def _category_paths() -> list[str]:
    configured = _secret('category_path', _secret('categories_path', ''))
    paths = [configured] if configured else []
    paths.extend(['/categorias/produtos', '/categorias'])
    out: list[str] = []
    for path in paths:
        value = str(path or '').strip()
        if value and value not in out:
            out.append(value)
    return out


def _category_id(item: dict[str, Any]) -> str:
    return str(item.get('id') or item.get('idCategoria') or item.get('codigo') or '').strip()


def _category_name(item: dict[str, Any]) -> str:
    return str(item.get('descricao') or item.get('nome') or item.get('name') or item.get('description') or '').strip()


def _resolve_or_create_category(token: dict[str, Any], category_name: str) -> str:
    name = _clean_text(category_name, 80)
    if not name:
        return ''
    key = name.lower()
    cache = _category_cache()
    if key in cache:
        return str(cache.get(key) or '')
    headers = _headers(token)
    for path in _category_paths():
        for params in ({'descricao': name}, {'nome': name}, {'criterio': name}, {'pesquisa': name}):
            try:
                response = requests.get(_url(path), headers=headers, params=params, timeout=CATEGORY_TIMEOUT)
                if response.status_code >= 400:
                    continue
                for item in _extract_items(response.json()):
                    item_id = _category_id(item)
                    item_name = _category_name(item)
                    if item_id and item_name.lower() == key:
                        cache[key] = item_id
                        return item_id
            except Exception:
                continue
    if _secret('auto_create_categories', '1').lower() not in {'1', 'true', 'sim', 'yes', 'on'}:
        cache[key] = ''
        return ''
    for path in _category_paths():
        for payload in ({'descricao': name}, {'nome': name}, {'descricao': name, 'tipo': 'P'}):
            try:
                response = requests.post(_url(path), headers=headers, json=payload, timeout=SEND_TIMEOUT)
                if response.status_code >= 400:
                    continue
                data = response.json() if str(response.text or '').strip() else {}
                item_id = _category_id(data) if isinstance(data, dict) else ''
                nested = data.get('data') or data.get('dados') if isinstance(data, dict) else None
                if isinstance(nested, dict):
                    item_id = item_id or _category_id(nested)
                items = _extract_items(data)
                if not item_id and items:
                    item_id = _category_id(items[0])
                if item_id:
                    cache[key] = item_id
                    add_audit_event('bling_smart_category_created', area='BLING_ENVIO', status='OK', details={'category': name, 'category_id': item_id, 'path': path, 'responsible_file': RESPONSIBLE_FILE})
                    return item_id
            except Exception as exc:
                add_audit_event('bling_smart_category_create_exception', area='BLING_ENVIO', status='AVISO', details={'category': name, 'error': str(exc)[:180], 'responsible_file': RESPONSIBLE_FILE})
    cache[key] = ''
    return ''


def _valid_brand(value: object) -> str:
    brand = _clean_text(value, 60).strip(' -|/.,;:')
    if not brand:
        return ''
    low = brand.lower()
    if any(term in low for term in BLOCKED_BRAND_TERMS):
        return ''
    if len(brand) < 2 or len(brand) > 60:
        return ''
    return brand


def _brand_from_title(title: object) -> str:
    text = f' {_clean_text(title, 180)} '
    normalized_text = text.lower().replace('-', ' ').replace('_', ' ')
    for brand in KNOWN_BRANDS:
        normalized_brand = brand.lower().replace('-', ' ').replace('_', ' ')
        if re.search(rf'(?<![a-z0-9]){re.escape(normalized_brand)}(?![a-z0-9])', normalized_text, flags=re.IGNORECASE):
            return _valid_brand(brand)
    for token in re.findall(r'\b[A-Z][A-Z0-9&.-]{1,14}\b', str(title or '')):
        if not _digits_only(token) and not token.upper().startswith(('USB', 'LED', 'HDMI', 'TYPE', 'TIPO')):
            candidate = _valid_brand(token)
            if candidate:
                return candidate
    return ''


def _resolve_brand(title: object, fallback_brand: object = '') -> str:
    from_title = _brand_from_title(title)
    if from_title:
        return from_title
    return _valid_brand(fallback_brand)


def _join_full_description_for_bling(*, short: object = '', complement: object = '', limit: int = 3500) -> str:
    parts = []
    for value in (short, complement):
        text = str(value or '').strip()
        if text and text not in parts:
            parts.append(text)
    full = '\n'.join(parts).strip()
    if len(full) > limit:
        return full[: limit - 3].rstrip() + '...'
    return full


def _put_if_number(payload: dict[str, Any], key: str, value: object) -> None:
    number = _number_value(value)
    if number is not None and number >= 0:
        payload[key] = _api_number(number)


def _base_payload(row: pd.Series, mapping: dict[str, str]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    raw_code = _value(row, mapping, 'codigo')
    gtin = _digits_only(_value(row, mapping, 'gtin'))
    code = _sanitize_code(raw_code or gtin)
    raw_description = _value(row, mapping, 'descricao')
    raw_short = _value(row, mapping, 'descricao_curta') or raw_description
    raw_complement = _value(row, mapping, 'descricao_complementar')
    enrichment = enrich_product_payload_fields(
        name=_value(row, mapping, 'nome'),
        description=raw_description,
        description_short=raw_short,
        description_complementary=raw_complement,
        code=code,
        gtin=gtin,
        category=_value(row, mapping, 'categoria'),
        images=_value(row, mapping, 'imagens'),
    )
    name = _clean_text(enrichment.name, 120)
    if len(name) < 2:
        return None, {'reason': 'nome_insuficiente', 'enrichment': enrichment}
    payload: dict[str, Any] = {'nome': name, 'tipo': 'P', 'situacao': 'A', 'formato': 'S'}
    if code:
        payload['codigo'] = code
    unit = _clean_text(_value(row, mapping, 'unidade') or 'UN', 6).upper()
    if re.fullmatch(r'[A-Z0-9]{1,6}', unit):
        payload['unidade'] = unit
    full_description = _join_full_description_for_bling(short=enrichment.description_short, complement=enrichment.description_complementary)
    if full_description and full_description.lower() != name.lower():
        payload['descricaoCurta'] = full_description
    price = _number_value(_value(row, mapping, 'preco'))
    if price is not None and price >= 0:
        payload['preco'] = _api_number(price)
    brand = _resolve_brand(name, _value(row, mapping, 'marca'))
    if brand:
        payload['marca'] = brand
    tributacao: dict[str, Any] = {}
    if len(gtin) in {8, 12, 13, 14}:
        payload['gtin'] = gtin
        tributacao['gtin'] = gtin
    ncm = _digits_only(_value(row, mapping, 'ncm'))
    if len(ncm) == 8:
        tributacao['ncm'] = ncm
    cest = _digits_only(_value(row, mapping, 'cest'))
    if len(cest) == 7:
        tributacao['cest'] = cest
    origem = _digits_only(_value(row, mapping, 'origem'))
    if origem:
        tributacao['origem'] = origem[:1]
    if tributacao:
        payload['tributacao'] = tributacao
    _put_if_number(payload, 'pesoLiquido', _value(row, mapping, 'peso_liquido'))
    _put_if_number(payload, 'pesoBruto', _value(row, mapping, 'peso_bruto'))
    dimensoes: dict[str, Any] = {}
    for source_field, bling_key in (('largura', 'largura'), ('altura', 'altura'), ('profundidade', 'profundidade')):
        number = _number_value(_value(row, mapping, source_field))
        if number is not None and number > 0:
            dimensoes[bling_key] = _api_number(number)
    if dimensoes:
        payload['dimensoes'] = dimensoes
    meta = {
        'category': enrichment.category,
        'images': list(enrichment.image_urls),
        'confidence': enrichment.confidence,
        'warnings': list(enrichment.warnings),
        'code': code,
        'gtin': gtin,
        'raw_code': str(raw_code or ''),
        'brand': brand,
        'brand_source': 'titulo' if _brand_from_title(name) else ('fallback' if brand else ''),
        'description_short_len': len(full_description or ''),
        'description_complementary_len': 0,
        'description_rule': 'descricao_completa_em_descricaoCurta_sem_descricaoComplementar',
        'formato': 'S',
        'rich_fields': sorted(payload.keys()),
    }
    return _clean_payload(payload), meta


def _payload_variants(token: dict[str, Any], row: pd.Series, mapping: dict[str, str]) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    base, meta = _base_payload(row, mapping)
    if not base:
        return []
    category = str(meta.get('category') or '').strip()
    category_id = _resolve_or_create_category(token, category) if category else ''
    images = list(meta.get('images') or [])
    full = dict(base)
    if category_id:
        full['categoria'] = {'id': category_id}
    elif category:
        full['categoria'] = {'descricao': category}
    if images:
        full['midia'] = {'imagens': [{'link': url} for url in images[:10]]}
    with_category = dict(base)
    if category_id:
        with_category['categoria'] = {'id': category_id}
    elif category:
        with_category['categoria'] = {'descricao': category}
    no_media = dict(with_category)
    variants: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    seen: set[str] = set()
    for label, payload in (
        ('smart_completo_todos_dados_site_categoria_imagem_gtin_dimensoes', full),
        ('smart_todos_dados_site_categoria_sem_imagem', no_media),
        ('smart_todos_dados_site_basico_sem_categoria_imagem', base),
        ('smart_nome_codigo_minimo_formato', {'nome': base.get('nome', 'Produto sem nome'), 'tipo': 'P', 'situacao': 'A', 'formato': 'S', **({'codigo': base['codigo']} if base.get('codigo') else {})}),
    ):
        cleaned = _clean_payload(payload)
        marker = repr(sorted(cleaned.items()))
        if cleaned and marker not in seen:
            strategy_meta = dict(meta)
            strategy_meta['category_id'] = category_id
            strategy_meta['strategy'] = label
            variants.append((label, cleaned, strategy_meta))
            seen.add(marker)
    return variants


def _smart_preview_payloads(df: pd.DataFrame, *, limit: int = 5) -> list[dict[str, Any]]:
    schema_error = _cadastro_schema_error(df)
    if schema_error:
        return [{'payload': {}, 'status': 'BLOQUEADO', 'motivo': schema_error}]
    token, _meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return _safe_preview_payloads(df, OP_CADASTRO, limit=limit)
    mapping = _column_map(df.columns)
    out: list[dict[str, Any]] = []
    for _index, row in df.fillna('').head(limit).iterrows():
        variants = _payload_variants(token, row, mapping)
        if variants:
            label, payload, meta = variants[0]
            out.append({'payload': payload, 'status': 'OK', 'motivo': f'BLINGSMARTCORE {label} · confiança {meta.get("confidence", 0)}/100 · campos {", ".join(meta.get("rich_fields", []))} · marca {meta.get("brand", "") or "não definida"} ({meta.get("brand_source", "") or "sem fonte"})'})
        else:
            out.append({'payload': {}, 'status': 'IGNORADO', 'motivo': 'Nome/código insuficiente para cadastro.'})
    return out


def preview_payloads(df: pd.DataFrame, operation: str, *, limit: int = 5) -> list[dict[str, Any]]:
    if normalize_operation(operation) == OP_CADASTRO:
        return _smart_preview_payloads(df, limit=limit)
    return _safe_preview_payloads(df, operation, limit=limit)


def _emit_progress(callback: Callable[[dict[str, Any]], None] | None, payload: dict[str, Any]) -> None:
    if not callback:
        return
    try:
        callback(payload)
    except Exception:
        pass


def _update_existing_product(token: dict[str, Any], product_id: str, variants: list[tuple[str, dict[str, Any], dict[str, Any]]]) -> tuple[bool, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    for strategy, payload, meta in variants:
        for method in ('PATCH', 'PUT'):
            try:
                response = requests.request(method, _url(f'/produtos/{product_id}'), headers=_headers(token), json=payload, timeout=SEND_TIMEOUT)
                attempts.append({'mode': 'update_existing', 'method': method, 'product_id': product_id, 'strategy': strategy, 'status': int(response.status_code), 'confidence': meta.get('confidence'), 'payload_keys': sorted(payload.keys()), 'response_preview': str(response.text or '')[:300]})
                if response.status_code < 400:
                    return True, attempts
                if response.status_code in {401, 403, 404}:
                    break
            except Exception as exc:
                attempts.append({'mode': 'update_existing', 'method': method, 'product_id': product_id, 'strategy': strategy, 'status': 'EXCEPTION', 'error': str(exc)[:240]})
    return False, attempts


def _send_cadastro_smart(df: pd.DataFrame, *, limit: int | None = None, progress_callback: Callable[[dict[str, Any]], None] | None = None) -> DirectSendResult:
    schema_error = _cadastro_schema_error(df)
    if schema_error:
        total = len(df) if isinstance(df, pd.DataFrame) else 0
        return DirectSendResult(total, 0, 0, total, (schema_error,), tuple())
    token, _meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return DirectSendResult(0, 0, 0, len(df) if isinstance(df, pd.DataFrame) else 0, ('Bling não conectado. Conecte o app antes de enviar direto.',))
    rows = df.fillna('').head(limit) if limit else df.fillna('')
    mapping = _column_map(rows.columns)
    total = len(rows)
    sent = failed = skipped = 0
    errors: list[str] = []
    create_path = _secret('product_create_path', '/produtos') or '/produtos'
    _emit_progress(progress_callback, {'stage': 'Iniciando cadastro inteligente', 'processed': 0, 'total': total, 'sent': 0, 'failed': 0, 'skipped': 0, 'progress': 0.0})
    for position, (index, row) in enumerate(rows.iterrows(), start=1):
        line = int(index) + 1 if isinstance(index, int) else position
        variants = _payload_variants(token, row, mapping)
        if not variants:
            skipped += 1
            if len(errors) < 8:
                errors.append(f'Linha {line}: nome/código insuficiente para cadastro.')
            _emit_progress(progress_callback, {'stage': 'Produto ignorado', 'processed': position, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': position / max(total, 1)})
            continue
        first_meta = variants[0][2]
        candidates = [first_meta.get('code'), first_meta.get('gtin'), first_meta.get('raw_code')]
        existing_id = _resolve_product_id(token, candidates)
        if existing_id:
            ok_update, update_attempts = _update_existing_product(token, existing_id, variants)
            if ok_update:
                sent += 1
                add_audit_event('bling_smart_cadastro_upsert_updated', area='BLING_ENVIO', status='OK', details={'line': line, 'product_id': existing_id, 'attempts': update_attempts[-3:], 'responsible_file': RESPONSIBLE_FILE})
                _emit_progress(progress_callback, {'stage': 'Atualizando produto existente no Bling', 'processed': position, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': position / max(total, 1)})
                continue
        ok = False
        attempts: list[dict[str, Any]] = []
        last_response: requests.Response | None = None
        for strategy, payload, meta in variants:
            try:
                response = requests.post(_url(create_path), headers=_headers(token), json=payload, timeout=SEND_TIMEOUT)
                last_response = response
                response_text = str(response.text or '')
                attempts.append({'mode': 'create', 'strategy': strategy, 'status': int(response.status_code), 'confidence': meta.get('confidence'), 'category': meta.get('category'), 'category_id': meta.get('category_id'), 'brand': meta.get('brand'), 'brand_source': meta.get('brand_source'), 'formato': meta.get('formato', 'S'), 'rich_fields': meta.get('rich_fields'), 'payload_keys': sorted(payload.keys()), 'response_preview': response_text[:500]})
                if response.status_code < 400:
                    ok = True
                    add_audit_event('bling_smart_cadastro_strategy_succeeded', area='BLING_ENVIO', status='OK', details={'line': line, 'strategy': strategy, 'meta': meta, 'responsible_file': RESPONSIBLE_FILE})
                    break
                if response.status_code == 400 and ('código' in response_text.lower() or 'codigo' in response_text.lower()):
                    resolved_after_error = _resolve_product_id(token, candidates)
                    if resolved_after_error:
                        ok_update, update_attempts = _update_existing_product(token, resolved_after_error, variants)
                        attempts.extend(update_attempts[-4:])
                        if ok_update:
                            ok = True
                            add_audit_event('bling_smart_cadastro_duplicate_code_updated', area='BLING_ENVIO', status='OK', details={'line': line, 'product_id': resolved_after_error, 'strategy': strategy, 'responsible_file': RESPONSIBLE_FILE})
                            break
                if response.status_code in {401, 403}:
                    break
            except Exception as exc:
                attempts.append({'mode': 'create', 'strategy': strategy, 'status': 'EXCEPTION', 'error': str(exc)[:240]})
        if ok:
            sent += 1
        else:
            failed += 1
            status = getattr(last_response, 'status_code', 'sem resposta')
            preview = str(getattr(last_response, 'text', '') or '')[:700]
            if len(errors) < 8:
                errors.append(f'Linha {line}: Bling recusou cadastro/upsert inteligente ({status}) após {len(variants)} tentativa(s). {preview}')
            add_audit_event('bling_smart_cadastro_failed', area='BLING_ENVIO', status='AVISO', details={'line': line, 'status': status, 'attempts': attempts[-8:], 'responsible_file': RESPONSIBLE_FILE})
        _emit_progress(progress_callback, {'stage': 'Cadastrando no Bling', 'processed': position, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': position / max(total, 1)})
    _emit_progress(progress_callback, {'stage': 'Cadastro inteligente concluído', 'processed': total, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': 1.0})
    add_audit_event('bling_smart_cadastro_finished', area='BLING_ENVIO', status='OK' if failed == 0 else 'PARCIAL', details={'attempted': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'mode': 'upsert_heuristic_todos_dados_site_categoria_imagem_gtin_dimensoes', 'responsible_file': RESPONSIBLE_FILE})
    return DirectSendResult(total, sent, failed, skipped, tuple(errors), tuple())


def send_dataframe_to_bling(df: pd.DataFrame, operation: str, *, limit: int | None = None, progress_callback: Callable[[dict[str, Any]], None] | None = None) -> DirectSendResult:
    if normalize_operation(operation) == OP_CADASTRO:
        return _send_cadastro_smart(df, limit=limit, progress_callback=progress_callback)
    return _safe_send_dataframe_to_bling(df, operation, limit=limit, progress_callback=progress_callback)


__all__ = ['DirectSendResult', 'is_direct_send_available', 'preview_payloads', 'send_dataframe_to_bling']
