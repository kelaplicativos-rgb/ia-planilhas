from __future__ import annotations

import re
from typing import Any, Callable, Iterable

import pandas as pd
import requests
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_direct_sender import (
    DirectSendResult,
    is_direct_send_available,
    preview_payloads as _raw_preview_payloads,
    send_dataframe_to_bling as _raw_send_dataframe_to_bling,
)
from bling_app_zero.core.bling_token_store import load_token
from bling_app_zero.core.operation_contract import OP_CADASTRO, OP_ESTOQUE, normalize_operation
from bling_app_zero.core.operation_safety_guard import require_rows_before_api

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_direct_sender_safe.py'
DEFAULT_API_BASE_URL = 'https://www.bling.com.br/Api/v3'
API_STOCK_DEPOSIT_KEY = 'bling_api_stock_deposit_name'
API_STOCK_DEPOSIT_ID_KEY = 'bling_api_stock_deposit_id'
API_STOCK_DEPOSIT_OPTIONS_KEY = 'bling_api_stock_deposit_options'
PRODUCT_RESOLUTION_CACHE_KEY = 'bling_safe_product_resolution_cache_v10'
CATEGORY_RESOLUTION_CACHE_KEY = 'bling_safe_category_resolution_cache_v5'
PRODUCT_LOOKUP_TIMEOUT = 12
CATEGORY_LOOKUP_TIMEOUT = 12
DEPOSIT_LOOKUP_TIMEOUT = 15
SEND_TIMEOUT = 30

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    'id': ('id', 'id produto', 'id_produto', 'id produto bling', 'id_produto_bling', 'id bling', 'id_bling', 'codigo bling', 'código bling', 'id produto bling api', 'id produto api'),
    'codigo': ('código', 'codigo', 'sku', 'ref', 'referencia', 'referência', 'codigo produto', 'código produto', 'cod produto', 'cod', 'cód', 'cód.', 'codigo fornecedor', 'código fornecedor'),
    'nome': ('nome', 'produto', 'título', 'titulo', 'nome produto', 'nome do produto', 'descrição produto', 'descricao produto'),
    'descricao': ('descrição', 'descricao', 'descrição curta', 'descricao curta', 'descrição do produto', 'descricao do produto', 'detalhes', 'descricao complementar', 'descrição complementar'),
    'preco': ('preço', 'preco', 'preço unitário', 'preco unitario', 'preço unitário (obrigatório)', 'preco unitario (obrigatorio)', 'valor', 'valor venda', 'preço de venda', 'preco de venda'),
    'gtin': ('gtin', 'ean', 'codigo de barras', 'código de barras', 'gtin/ean'),
    'marca': ('marca', 'fabricante'),
    'unidade': ('unidade', 'un'),
    'ncm': ('ncm',),
    'quantidade': ('quantidade', 'saldo', 'estoque', 'balanço', 'balanco', 'qtd', 'qtde', 'stock'),
    'deposito': ('depósito', 'deposito', 'nome depósito', 'nome deposito', 'depósito padrão', 'deposito padrao'),
    'categoria': ('categoria', 'categoria produto', 'categoria do produto', 'departamento', 'grupo'),
    'imagens': ('imagens', 'imagem', 'url imagem', 'url imagens', 'fotos', 'foto'),
}


def _secret(name: str, default: str = '') -> str:
    try:
        bling = st.secrets.get('bling', {})
        value = bling.get(name, default) if hasattr(bling, 'get') else default
        return str(value or default).strip()
    except Exception:
        return default


def _url(path: str) -> str:
    if str(path or '').startswith(('http://', 'https://')):
        return str(path)
    base = (_secret('api_base_url', DEFAULT_API_BASE_URL) or DEFAULT_API_BASE_URL).rstrip('/')
    return base + '/' + str(path or '').lstrip('/')


def _headers(token: dict[str, Any]) -> dict[str, str]:
    return {'Accept': 'application/json', 'Content-Type': 'application/json', 'Authorization': f"Bearer {token.get('access_token')}"}


def _norm(value: object) -> str:
    text = str(value or '').strip().lower()
    for old, new in {'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c'}.items():
        text = text.replace(old, new)
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', text)).strip()


def _column_map(columns: Iterable[object]) -> dict[str, str]:
    normalized = {_norm(column): str(column) for column in columns}
    out: dict[str, str] = {}
    for field, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            column = normalized.get(_norm(alias))
            if column:
                out[field] = column
                break
    return out


def _value(row: pd.Series, mapping: dict[str, str], field: str) -> str:
    column = mapping.get(field)
    if not column:
        return ''
    value = row.get(column, '')
    return '' if pd.isna(value) else str(value or '').strip()


def _clean_text(value: object, limit: int = 120) -> str:
    text = str(value or '').replace('\u200b', '').replace('\ufeff', '').strip()
    text = re.sub(r'<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()[:limit]


def _digits_only(value: object) -> str:
    return re.sub(r'\D+', '', str(value or ''))


def _is_ean_like(value: object) -> bool:
    return len(_digits_only(value)) in {8, 12, 13, 14}


def _number_value(value: object) -> float | None:
    text = str(value or '').strip().replace('R$', '').replace('\xa0', '').replace(' ', '')
    if not text:
        return None
    text = text.replace('.', '').replace(',', '.') if ',' in text and '.' in text else text.replace(',', '.')
    text = re.sub(r'[^0-9.\-]+', '', text)
    try:
        return float(text) if text not in {'', '-', '.', '-.'} else None
    except Exception:
        return None


def _api_number(value: float) -> int | float:
    number = float(value)
    return int(number) if number.is_integer() else round(number, 4)


def _unique_non_empty(values: Iterable[object]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or '').strip()
        key = text.lower()
        if text and key not in seen:
            out.append(text)
            seen.add(key)
    return out


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in payload.items():
        if str(key).startswith('_') or value in ('', None, {}, []):
            continue
        if isinstance(value, dict):
            nested = _clean_payload(value)
            if nested:
                clean[key] = nested
        elif isinstance(value, list):
            items = [item for item in value if item not in ('', None, {}, [])]
            if items:
                clean[key] = items
        else:
            clean[key] = value
    return clean


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
    return [payload] if payload.get('id') or payload.get('idCategoria') else []


def _session_cache(key: str) -> dict[str, str]:
    cache = st.session_state.get(key)
    if not isinstance(cache, dict):
        cache = {}
        st.session_state[key] = cache
    return cache


def _item_identifiers(item: dict[str, Any]) -> list[str]:
    trib = item.get('tributacao') if isinstance(item.get('tributacao'), dict) else {}
    return _unique_non_empty([
        item.get('id'),
        item.get('idProduto'),
        item.get('codigo'),
        item.get('sku'),
        item.get('codigoProduto'),
        item.get('gtin'),
        item.get('ean'),
        item.get('codigoBarras'),
        trib.get('gtin'),
        trib.get('ean'),
        trib.get('codigoBarras'),
    ])


def _resolve_product_by_candidate(token: dict[str, Any], candidate: str) -> str:
    candidate = str(candidate or '').strip()
    if not candidate:
        return ''
    cache = _session_cache(PRODUCT_RESOLUTION_CACHE_KEY)
    key = candidate.lower()
    if key in cache:
        return str(cache.get(key) or '')

    if candidate.isdigit() and len(candidate) >= 6:
        try:
            response = requests.get(_url(f'/produtos/{candidate}'), headers=_headers(token), timeout=PRODUCT_LOOKUP_TIMEOUT)
            if response.status_code < 400:
                data = response.json() if str(response.text or '').strip() else {}
                items = _extract_items(data)
                if items or isinstance(data, dict):
                    item = items[0] if items else data
                    item_id = str(item.get('id') or item.get('idProduto') or candidate).strip()
                    if item_id:
                        cache[key] = item_id
                        add_audit_event('bling_safe_product_resolved_by_direct_id_before_send', area='BLING_ENVIO', status='OK', details={'candidate': candidate, 'product_id': item_id, 'responsible_file': RESPONSIBLE_FILE})
                        return item_id
        except Exception as exc:
            add_audit_event('bling_safe_product_direct_id_lookup_exception', area='BLING_ENVIO', status='AVISO', details={'candidate': candidate, 'error': str(exc)[:180], 'responsible_file': RESPONSIBLE_FILE})

    lookup_path = _secret('product_lookup_path', '/produtos') or '/produtos'
    for params in ({'codigo': candidate}, {'criterio': candidate}, {'pesquisa': candidate}):
        try:
            response = requests.get(_url(lookup_path), headers=_headers(token), params=params, timeout=PRODUCT_LOOKUP_TIMEOUT)
            if response.status_code >= 400:
                continue
            items = _extract_items(response.json())
            for item in items:
                item_id = str(item.get('id') or item.get('idProduto') or '').strip()
                identifiers = [item_identifier.lower() for item_identifier in _item_identifiers(item)]
                if item_id and (candidate.lower() in identifiers or len(items) == 1):
                    cache[key] = item_id
                    add_audit_event('bling_safe_product_resolved_before_send', area='BLING_ENVIO', status='OK', details={'candidate': candidate, 'product_id': item_id, 'params': params, 'responsible_file': RESPONSIBLE_FILE})
                    return item_id
        except Exception as exc:
            add_audit_event('bling_safe_product_lookup_exception', area='BLING_ENVIO', status='AVISO', details={'candidate': candidate, 'error': str(exc)[:180], 'responsible_file': RESPONSIBLE_FILE})
            break
    cache[key] = ''
    return ''


def _row_candidates(row: pd.Series, mapping: dict[str, str]) -> list[str]:
    return _unique_non_empty([_value(row, mapping, 'id'), _value(row, mapping, 'codigo'), _value(row, mapping, 'gtin')])


def _category_name_from_row(row: pd.Series, mapping: dict[str, str]) -> str:
    text = _clean_text(_value(row, mapping, 'categoria'), 120)
    if not text:
        return ''
    parts = [part.strip() for part in re.split(r'[>/|;]+', text) if part.strip()]
    parts = [part for part in parts if _norm(part) not in {'home', 'inicio', 'loja', 'produtos', 'produto'}]
    return _clean_text(parts[-1] if parts else text, 80)


def _category_paths() -> list[str]:
    configured = _secret('category_path', _secret('categories_path', ''))
    return _unique_non_empty([configured, '/categorias/produtos', '/categorias'])


def _category_item_id(item: dict[str, Any]) -> str:
    return str(item.get('id') or item.get('idCategoria') or item.get('codigo') or '').strip()


def _category_item_name(item: dict[str, Any]) -> str:
    return str(item.get('descricao') or item.get('nome') or item.get('name') or item.get('description') or '').strip()


def _category_response_id(data: Any) -> str:
    if isinstance(data, dict):
        direct = _category_item_id(data)
        if direct:
            return direct
        for key in ('data', 'dados', 'categoria', 'result'):
            nested = _category_response_id(data.get(key))
            if nested:
                return nested
    if isinstance(data, list) and data:
        return _category_response_id(data[0])
    return ''


def _resolve_category_id(token: dict[str, Any], category_name: str, *, line: int | None = None, product_code: str = '') -> str:
    name = _clean_text(category_name, 80)
    if not name:
        return ''
    cache = _session_cache(CATEGORY_RESOLUTION_CACHE_KEY)
    key = name.lower()
    if key in cache:
        return str(cache.get(key) or '')
    headers = _headers(token)
    lookup_errors: list[str] = []
    for path in _category_paths():
        for params in ({'descricao': name}, {'nome': name}, {'criterio': name}, {'pesquisa': name}):
            try:
                response = requests.get(_url(path), headers=headers, params=params, timeout=CATEGORY_LOOKUP_TIMEOUT)
                if response.status_code >= 400:
                    lookup_errors.append(f'{path} GET {response.status_code}')
                    continue
                for item in _extract_items(response.json()):
                    item_id, item_name = _category_item_id(item), _category_item_name(item)
                    if item_id and item_name and _norm(item_name) == _norm(name):
                        cache[key] = item_id
                        add_audit_event('bling_safe_category_resolved_by_id', area='BLING_ENVIO', status='OK', details={'line': line, 'product_code': product_code, 'category': name, 'category_id': item_id, 'path': path, 'responsible_file': RESPONSIBLE_FILE})
                        return item_id
            except Exception as exc:
                lookup_errors.append(f'{path}: {str(exc)[:120]}')
    if _secret('auto_create_categories', '1').lower() not in {'1', 'true', 'sim', 'yes', 'on'}:
        cache[key] = ''
        add_audit_event('bling_safe_category_auto_create_disabled', area='BLING_ENVIO', status='IGNORADO', details={'line': line, 'product_code': product_code, 'category': name, 'lookup_errors': lookup_errors[:6], 'responsible_file': RESPONSIBLE_FILE})
        return ''
    create_errors: list[str] = []
    for path in _category_paths():
        for payload in ({'descricao': name}, {'nome': name}, {'descricao': name, 'tipo': 'P'}):
            try:
                response = requests.post(_url(path), headers=headers, json=payload, timeout=SEND_TIMEOUT)
                if response.status_code >= 400:
                    create_errors.append(f'{path} POST {response.status_code}: {str(response.text or "")[:180]}')
                    continue
                item_id = _category_response_id(response.json() if str(response.text or '').strip() else {})
                if item_id:
                    cache[key] = item_id
                    add_audit_event('bling_safe_category_created_by_id', area='BLING_ENVIO', status='OK', details={'line': line, 'product_code': product_code, 'category': name, 'category_id': item_id, 'path': path, 'payload': payload, 'responsible_file': RESPONSIBLE_FILE})
                    return item_id
            except Exception as exc:
                create_errors.append(f'{path}: {str(exc)[:180]}')
    cache[key] = ''
    add_audit_event('bling_safe_category_not_resolved', area='BLING_ENVIO', status='AVISO', details={'line': line, 'product_code': product_code, 'category': name, 'paths': _category_paths(), 'lookup_errors': lookup_errors[:6], 'create_errors': create_errors[:6], 'responsible_file': RESPONSIBLE_FILE})
    return ''


def _valid_image_urls(raw: str) -> list[str]:
    urls: list[str] = []
    for piece in re.split(r'[|,;\n]+', str(raw or '')):
        url = piece.strip()
        if not url.lower().startswith(('http://', 'https://')):
            continue
        if '@' in url.rsplit('/', 1)[-1] and not re.search(r'\.(png|jpg|jpeg|webp)(\?|$)', url.lower()):
            continue
        if url not in urls:
            urls.append(url)
    return urls[:5]


def _load_stock_deposits(token: dict[str, Any]) -> list[dict[str, str]]:
    cached = st.session_state.get(API_STOCK_DEPOSIT_OPTIONS_KEY)
    if isinstance(cached, list) and cached:
        return [item for item in cached if isinstance(item, dict)]
    deposits: list[dict[str, str]] = []
    errors: list[str] = []
    for path in _unique_non_empty([_secret('stock_deposits_path', ''), '/estoques/depositos', '/depositos', '/estoque/depositos']):
        try:
            response = requests.get(_url(path), headers={'Accept': 'application/json', 'Authorization': f"Bearer {token.get('access_token')}"}, timeout=DEPOSIT_LOOKUP_TIMEOUT)
            if response.status_code >= 400:
                errors.append(f'{path}: HTTP {response.status_code}')
                continue
            for item in _extract_items(response.json()):
                nested = item.get('deposito') if isinstance(item.get('deposito'), dict) else {}
                deposit_id = str(item.get('id') or item.get('idDeposito') or item.get('id_deposito') or item.get('codigo') or nested.get('id') or nested.get('idDeposito') or '').strip()
                name = str(item.get('descricao') or item.get('nome') or item.get('name') or item.get('description') or nested.get('descricao') or nested.get('nome') or '').strip()
                if deposit_id or name:
                    deposits.append({'id': deposit_id, 'nome': name})
            if deposits:
                st.session_state[API_STOCK_DEPOSIT_OPTIONS_KEY] = deposits
                add_audit_event('bling_safe_stock_deposits_loaded', area='BLING_ENVIO', status='OK', details={'path': path, 'count': len(deposits), 'responsible_file': RESPONSIBLE_FILE})
                return deposits
        except Exception as exc:
            errors.append(f'{path}: {exc}')
    add_audit_event('bling_safe_stock_deposits_load_failed', area='BLING_ENVIO', status='AVISO', details={'errors': errors[:4], 'responsible_file': RESPONSIBLE_FILE})
    return []


def _resolve_deposit_id(token: dict[str, Any], preferred_name: str = '') -> str:
    current = str(st.session_state.get(API_STOCK_DEPOSIT_ID_KEY) or _secret('stock_deposit_id', '') or '').strip()
    if current:
        return current
    wanted = str(preferred_name or st.session_state.get(API_STOCK_DEPOSIT_KEY) or _secret('stock_deposit_name', _secret('default_stock_deposit_name', '')) or '').strip().lower()
    deposits = _load_stock_deposits(token)
    for item in deposits:
        deposit_id = str(item.get('id') or '').strip()
        name = str(item.get('nome') or '').strip().lower()
        if deposit_id and wanted and (wanted == name or wanted == deposit_id.lower()):
            st.session_state[API_STOCK_DEPOSIT_ID_KEY] = deposit_id
            return deposit_id
    if len(deposits) == 1 and str(deposits[0].get('id') or '').strip():
        deposit_id = str(deposits[0].get('id') or '').strip()
        st.session_state[API_STOCK_DEPOSIT_ID_KEY] = deposit_id
        return deposit_id
    return ''


def _stock_payload(product_id: str, deposit_id: str, quantity: float) -> dict[str, Any]:
    return {'produto': {'id': str(product_id)}, 'deposito': {'id': str(deposit_id)}, 'operacao': 'B', 'quantidade': _api_number(quantity)}


def _stock_endpoint_attempts(product_id: str) -> list[tuple[str, str]]:
    raw = [((_secret('stock_update_method', 'POST') or 'POST').upper(), _secret('stock_write_path', '/estoques/saldos') or '/estoques/saldos'), ('POST', '/estoques/saldos'), ('POST', '/estoques'), ('PUT', f'/estoques/saldos/{product_id}'), ('PATCH', f'/estoques/saldos/{product_id}')]
    out: list[tuple[str, str]] = []
    for method, path in raw:
        path = str(path or '').replace('{id}', product_id).replace('{idProduto}', product_id)
        if path and '{' not in path and (method, path) not in out:
            out.append((method, path))
    return out


def _emit_progress(callback: Callable[[dict[str, Any]], None] | None, payload: dict[str, Any]) -> None:
    if callback:
        try:
            callback(payload)
        except Exception:
            pass


def _base_cadastro_payload(row: pd.Series, mapping: dict[str, str]) -> dict[str, Any] | None:
    codigo = _clean_text(_value(row, mapping, 'codigo') or _value(row, mapping, 'gtin'), 80)
    nome_raw = _clean_text(_value(row, mapping, 'nome'), 120)
    descricao = _clean_text(_value(row, mapping, 'descricao'), 1000)
    nome = descricao[:120] if (_is_ean_like(nome_raw) and descricao) else nome_raw
    nome = nome or codigo or 'Produto sem nome'
    if len(nome) < 2:
        return None
    payload: dict[str, Any] = {'nome': nome, 'codigo': codigo or nome[:80], 'tipo': 'P', 'situacao': 'A', 'unidade': _clean_text(_value(row, mapping, 'unidade') or 'UN', 6) or 'UN'}
    if descricao and descricao.lower() != nome.lower():
        payload['descricaoCurta'] = descricao
    preco = _number_value(_value(row, mapping, 'preco'))
    if preco is not None and preco >= 0:
        payload['preco'] = _api_number(preco)
    marca = _clean_text(_value(row, mapping, 'marca'), 60)
    if marca and not marca.lower().startswith(('mega center', 'stoqui')):
        payload['marca'] = marca
    ncm = _digits_only(_value(row, mapping, 'ncm'))
    if len(ncm) == 8:
        payload['tributacao'] = {'ncm': ncm}
    return _clean_payload(payload)


def _cadastro_payload_variants(token: dict[str, Any], row: pd.Series, mapping: dict[str, str], *, line: int | None = None) -> list[tuple[str, dict[str, Any]]]:
    base = _base_cadastro_payload(row, mapping)
    if not base:
        return []
    category_name = _category_name_from_row(row, mapping)
    code = _clean_text(_value(row, mapping, 'codigo') or _value(row, mapping, 'gtin'), 80)
    category_id = _resolve_category_id(token, category_name, line=line, product_code=code) if category_name else ''
    category_payload = {'id': category_id} if category_id else {}
    image_urls = _valid_image_urls(_value(row, mapping, 'imagens'))
    full = dict(base)
    with_category = dict(base)
    if category_payload:
        full['categoria'] = category_payload
        with_category['categoria'] = category_payload
    if image_urls:
        full['midia'] = {'imagens': [{'link': url} for url in image_urls]}
    variants: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for label, payload in (('completo_categoria_id_imagem', full), ('categoria_id_sem_imagem', with_category), ('minimo_sem_categoria_imagem', base)):
        cleaned = _clean_payload(payload)
        marker = repr(sorted(cleaned.items()))
        if cleaned and marker not in seen:
            variants.append((label, cleaned))
            seen.add(marker)
    return variants


def _cadastro_preview_payloads(df: pd.DataFrame, *, limit: int = 5) -> list[dict[str, Any]]:
    token, _meta = load_token()
    mapping = _column_map(df.columns)
    previews: list[dict[str, Any]] = []
    for position, (_index, row) in enumerate(df.fillna('').head(limit).iterrows(), start=1):
        if isinstance(token, dict) and token.get('access_token'):
            variants = _cadastro_payload_variants(token, row, mapping, line=position)
            payload = variants[0][1] if variants else None
            category = payload.get('categoria', {}) if isinstance(payload, dict) else {}
            reason = 'Categoria API: ID resolvido' if isinstance(category, dict) and category.get('id') else 'Categoria API: não resolvida ou ausente'
        else:
            payload = _base_cadastro_payload(row, mapping)
            reason = 'Bling não conectado: preview sem resolução de categoria por API.' if payload else 'Nome/código insuficiente para cadastro.'
        previews.append({'payload': payload or {}, 'status': 'OK' if payload else 'IGNORADO', 'motivo': reason})
    return previews


def _stock_preview_payloads(df: pd.DataFrame, *, limit: int = 5) -> list[dict[str, Any]]:
    token, _meta = load_token()
    mapping = _column_map(df.columns)
    previews: list[dict[str, Any]] = []
    if not isinstance(token, dict) or not token.get('access_token'):
        return [{'payload': {}, 'status': 'IGNORADO', 'motivo': 'Bling não conectado.'}]
    deposit_id = _resolve_deposit_id(token)
    for _index, row in df.fillna('').head(limit).iterrows():
        quantity = _number_value(_value(row, mapping, 'quantidade'))
        product_id = ''
        for candidate in _row_candidates(row, mapping):
            product_id = _resolve_product_by_candidate(token, candidate)
            if product_id:
                break
        if not product_id:
            previews.append({'payload': {}, 'status': 'IGNORADO', 'motivo': 'Produto não resolvido no Bling por ID/Código/SKU/GTIN.'})
        elif not deposit_id:
            previews.append({'payload': {}, 'status': 'IGNORADO', 'motivo': 'Depósito não resolvido no Bling.'})
        elif quantity is None:
            previews.append({'payload': {}, 'status': 'IGNORADO', 'motivo': 'Quantidade/saldo inválido.'})
        else:
            previews.append({'payload': _stock_payload(product_id, deposit_id, quantity), 'status': 'OK', 'motivo': ''})
    return previews


def preview_payloads(df: pd.DataFrame, operation: str, *, limit: int = 5) -> list[dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    normalized = normalize_operation(operation)
    if normalized == OP_CADASTRO:
        return _cadastro_preview_payloads(df, limit=limit)
    if normalized == OP_ESTOQUE:
        return _stock_preview_payloads(df, limit=limit)
    return _raw_preview_payloads(df, operation, limit=limit)


def _blocked_empty_result(operation: str, progress_callback: Callable[[dict[str, Any]], None] | None = None) -> DirectSendResult:
    normalized = normalize_operation(operation)
    decision = require_rows_before_api(operation=normalized)
    message = decision.message or 'Envio ao Bling bloqueado: sender seguro recebeu origem vazia.'
    _emit_progress(progress_callback, {'stage': 'Envio bloqueado antes da API', 'operation': normalized, 'processed': 0, 'total': 0, 'sent': 0, 'failed': 0, 'skipped': 0, 'progress': 1.0, 'blocked_before_api': True, 'reason': decision.reason or 'sem_linhas'})
    add_audit_event('bling_safe_sender_blocked_empty_before_api', area='BLING_ENVIO', status='BLOQUEADO', details={'operation': normalized, 'message': message, 'reason': decision.reason or 'sem_linhas', 'decision_details': decision.details or {}, 'responsible_file': RESPONSIBLE_FILE})
    return DirectSendResult(0, 0, 0, 0, (message,), tuple())


def _send_cadastro_dataframe_to_bling(df: pd.DataFrame, *, limit: int | None = None, progress_callback: Callable[[dict[str, Any]], None] | None = None) -> DirectSendResult:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return _blocked_empty_result(OP_CADASTRO, progress_callback)
    token, _meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return DirectSendResult(0, 0, 0, len(df), ('Bling não conectado. Conecte o app antes de enviar direto.',))
    rows = df.fillna('').head(limit) if limit else df.fillna('')
    mapping = _column_map(rows.columns)
    total = len(rows)
    sent = failed = skipped = 0
    errors: list[str] = []
    create_path = _secret('product_create_path', '/produtos') or '/produtos'
    _emit_progress(progress_callback, {'stage': 'Iniciando cadastro', 'processed': 0, 'total': total, 'sent': 0, 'failed': 0, 'skipped': 0, 'progress': 0.0})
    for position, (index, row) in enumerate(rows.iterrows(), start=1):
        line = int(index) + 1 if isinstance(index, int) else position
        variants = _cadastro_payload_variants(token, row, mapping, line=line)
        if not variants:
            skipped += 1
            if len(errors) < 8:
                errors.append(f'Linha {line}: nome/código insuficiente para cadastro.')
            continue
        ok = False
        attempt_logs: list[dict[str, Any]] = []
        last_response: requests.Response | None = None
        for strategy, payload in variants:
            try:
                response = requests.post(_url(create_path), headers=_headers(token), json=payload, timeout=SEND_TIMEOUT)
                last_response = response
                category = payload.get('categoria') if isinstance(payload.get('categoria'), dict) else {}
                attempt_logs.append({'strategy': strategy, 'status': int(response.status_code), 'category_id': category.get('id', ''), 'payload_keys': sorted(payload.keys()), 'response_preview': str(response.text or '')[:300]})
                if response.status_code < 400:
                    ok = True
                    add_audit_event('bling_safe_cadastro_strategy_succeeded', area='BLING_ENVIO', status='OK', details={'line': line, 'strategy': strategy, 'category_id': category.get('id', ''), 'attempts': attempt_logs[-3:], 'responsible_file': RESPONSIBLE_FILE})
                    break
                if response.status_code in {401, 403}:
                    break
            except Exception as exc:
                attempt_logs.append({'strategy': strategy, 'status': 'EXCEPTION', 'error': str(exc)[:240], 'payload': payload})
        if ok:
            sent += 1
        else:
            failed += 1
            status = getattr(last_response, 'status_code', 'sem resposta')
            preview = str(getattr(last_response, 'text', '') or '')[:500]
            if len(errors) < 8:
                errors.append(f'Linha {line}: Bling recusou cadastro ({status}) após {len(variants)} tentativa(s). {preview}')
            add_audit_event('bling_safe_cadastro_payload_failed', area='BLING_ENVIO', status='AVISO', details={'line': line, 'status': status, 'attempts': attempt_logs[-5:], 'responsible_file': RESPONSIBLE_FILE})
        _emit_progress(progress_callback, {'stage': 'Cadastrando no Bling', 'processed': position, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': position / max(total, 1)})
    _emit_progress(progress_callback, {'stage': 'Cadastro concluído', 'processed': total, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': 1.0})
    add_audit_event('bling_safe_cadastro_send_finished', area='BLING_ENVIO', status='OK' if failed == 0 else 'PARCIAL', details={'attempted': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'payload_mode': 'category_id_only_no_description_fallback_with_audit_empty_guarded', 'responsible_file': RESPONSIBLE_FILE})
    return DirectSendResult(total, sent, failed, skipped, tuple(errors), tuple())


def _send_stock_dataframe_to_bling(df: pd.DataFrame, *, limit: int | None = None, progress_callback: Callable[[dict[str, Any]], None] | None = None) -> DirectSendResult:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return _blocked_empty_result(OP_ESTOQUE, progress_callback)
    token, _meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return DirectSendResult(0, 0, 0, len(df), ('Bling não conectado. Conecte o app antes de enviar direto.',))
    rows = df.fillna('').head(limit) if limit else df.fillna('')
    mapping = _column_map(rows.columns)
    total = len(rows)
    sent = failed = skipped = 0
    errors: list[str] = []
    not_found: list[int] = []
    _emit_progress(progress_callback, {'stage': 'Iniciando envio', 'processed': 0, 'total': total, 'sent': 0, 'failed': 0, 'skipped': 0, 'progress': 0.0})
    default_deposit_id = _resolve_deposit_id(token)
    for position, (index, row) in enumerate(rows.iterrows(), start=1):
        line = int(index) + 1 if isinstance(index, int) else position
        quantity = _number_value(_value(row, mapping, 'quantidade'))
        if quantity is None:
            skipped += 1
            if len(errors) < 8:
                errors.append(f'Linha {line}: quantidade/saldo ausente ou inválido.')
            continue
        product_id = ''
        for candidate in _row_candidates(row, mapping):
            product_id = _resolve_product_by_candidate(token, candidate)
            if product_id:
                break
        if not product_id:
            failed += 1
            not_found.append(int(index) if isinstance(index, int) else position - 1)
            if len(errors) < 8:
                errors.append(f'Linha {line}: produto não encontrado no Bling por ID/Código/SKU/GTIN.')
            continue
        deposit_id = _resolve_deposit_id(token, _value(row, mapping, 'deposito')) or default_deposit_id
        if not deposit_id:
            failed += 1
            if len(errors) < 8:
                errors.append(f'Linha {line}: depósito não resolvido no Bling.')
            continue
        payload = _stock_payload(product_id, deposit_id, quantity)
        last_response: requests.Response | None = None
        ok = False
        attempts: list[dict[str, Any]] = []
        for method, path in _stock_endpoint_attempts(product_id):
            try:
                response = requests.request(method, _url(path), headers=_headers(token), json=payload, timeout=SEND_TIMEOUT)
                last_response = response
                attempts.append({'method': method, 'path': path, 'status': response.status_code, 'payload': payload, 'response_preview': str(response.text or '')[:180]})
                if response.status_code < 400:
                    ok = True
                    break
                if response.status_code in {401, 403}:
                    break
            except Exception as exc:
                attempts.append({'method': method, 'path': path, 'status': 'EXCEPTION', 'error': str(exc)[:180]})
        if ok:
            sent += 1
        else:
            failed += 1
            status = getattr(last_response, 'status_code', 'sem resposta')
            preview = str(getattr(last_response, 'text', '') or '')[:180]
            first_endpoint = attempts[0].get('path') if attempts else '/estoques/saldos'
            if len(errors) < 8:
                errors.append(f'Linha {line}: Bling recusou estoque ({status}). Primeiro endpoint tentado: {first_endpoint}. {preview}')
            add_audit_event('bling_safe_stock_clean_payload_failed', area='BLING_ENVIO', status='AVISO', details={'line': line, 'product_id': product_id, 'deposit_id': deposit_id, 'quantity': quantity, 'payload': payload, 'attempts': attempts[-6:], 'responsible_file': RESPONSIBLE_FILE})
        _emit_progress(progress_callback, {'stage': 'Enviando ao Bling', 'processed': position, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': position / max(total, 1)})
    _emit_progress(progress_callback, {'stage': 'Envio concluído', 'processed': total, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': 1.0})
    add_audit_event('bling_safe_stock_clean_send_finished', area='BLING_ENVIO', status='OK' if failed == 0 else 'PARCIAL', details={'attempted': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'not_found_count': len(not_found), 'empty_guarded': True, 'responsible_file': RESPONSIBLE_FILE})
    return DirectSendResult(total, sent, failed, skipped, tuple(errors), tuple(not_found))


def send_dataframe_to_bling(df: pd.DataFrame, operation: str, *, limit: int | None = None, progress_callback: Callable[[dict[str, Any]], None] | None = None) -> DirectSendResult:
    normalized = normalize_operation(operation)
    if not isinstance(df, pd.DataFrame) or df.empty:
        return _blocked_empty_result(normalized, progress_callback)
    if normalized == OP_CADASTRO:
        return _send_cadastro_dataframe_to_bling(df, limit=limit, progress_callback=progress_callback)
    if normalized == OP_ESTOQUE:
        return _send_stock_dataframe_to_bling(df, limit=limit, progress_callback=progress_callback)
    return _raw_send_dataframe_to_bling(df, operation, limit=limit, progress_callback=progress_callback)


__all__ = ['DirectSendResult', 'is_direct_send_available', 'preview_payloads', 'send_dataframe_to_bling']
