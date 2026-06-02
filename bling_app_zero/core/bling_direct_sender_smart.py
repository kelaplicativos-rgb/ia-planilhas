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
from bling_app_zero.core.operation_contract import OP_CADASTRO, OP_ESTOQUE, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_direct_sender_smart.py'
DEFAULT_API_BASE_URL = 'https://www.bling.com.br/Api/v3'
SEND_TIMEOUT = 30
CATEGORY_TIMEOUT = 15
CATEGORY_CACHE_KEY = 'bling_smart_sender_category_cache_v1'

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    'codigo': ('código', 'codigo', 'sku', 'ref', 'referencia', 'referência', 'codigo produto', 'código produto', 'cod produto', 'cod'),
    'nome': ('nome', 'produto', 'título', 'titulo', 'nome produto', 'nome do produto', 'descrição produto', 'descricao produto'),
    'descricao': ('descrição', 'descricao', 'descrição curta', 'descricao curta', 'descrição do produto', 'descricao do produto', 'detalhes', 'descricao complementar', 'descrição complementar'),
    'preco': ('preço', 'preco', 'preço unitário', 'preco unitario', 'preço unitário (obrigatório)', 'preco unitario (obrigatorio)', 'valor', 'valor venda', 'preço de venda', 'preco de venda'),
    'gtin': ('gtin', 'ean', 'codigo de barras', 'código de barras', 'gtin/ean'),
    'marca': ('marca', 'fabricante'),
    'unidade': ('unidade', 'un'),
    'ncm': ('ncm',),
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


def _api_base_url() -> str:
    return (_secret('api_base_url', DEFAULT_API_BASE_URL) or DEFAULT_API_BASE_URL).rstrip('/')


def _url(path: str) -> str:
    if path.startswith(('http://', 'https://')):
        return path
    return _api_base_url() + '/' + path.lstrip('/')


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
    text = str(value or '').strip().replace('R$', '').replace(' ', '')
    if not text:
        return None
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    else:
        text = text.replace(',', '.')
    try:
        return float(text)
    except Exception:
        return None


def _digits_only(value: object) -> str:
    return re.sub(r'\D+', '', str(value or ''))


def _clean_text(value: object, limit: int = 120) -> str:
    text = str(value or '').replace('\u200b', '').replace('\ufeff', '').strip()
    text = re.sub(r'\s+', ' ', text).strip()
    return text[:limit]


def _clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in payload.items():
        if value in ('', None, {}, []):
            continue
        if isinstance(value, dict):
            nested = {k: v for k, v in value.items() if v not in ('', None, {}, [])}
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


def _category_cache() -> dict[str, str]:
    cache = st.session_state.get(CATEGORY_CACHE_KEY)
    if not isinstance(cache, dict):
        cache = {}
        st.session_state[CATEGORY_CACHE_KEY] = cache
    return cache


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

    payloads = ({'descricao': name}, {'nome': name}, {'descricao': name, 'tipo': 'P'})
    for path in _category_paths():
        for payload in payloads:
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


def _base_payload(row: pd.Series, mapping: dict[str, str]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    code = _clean_text(_value(row, mapping, 'codigo') or _value(row, mapping, 'gtin'), 80)
    gtin = _digits_only(_value(row, mapping, 'gtin'))
    enrichment = enrich_product_payload_fields(
        name=_value(row, mapping, 'nome'),
        description=_value(row, mapping, 'descricao'),
        code=code,
        gtin=gtin,
        category=_value(row, mapping, 'categoria'),
        images=_value(row, mapping, 'imagens'),
    )
    name = _clean_text(enrichment.name, 120)
    if len(name) < 2:
        return None, {'reason': 'nome_insuficiente', 'enrichment': enrichment}

    payload: dict[str, Any] = {
        'nome': name,
        'codigo': code or name[:80],
        'tipo': 'P',
        'situacao': 'A',
        'unidade': _clean_text(_value(row, mapping, 'unidade') or 'UN', 6) or 'UN',
    }
    if enrichment.description and enrichment.description.lower() != name.lower():
        payload['descricaoCurta'] = enrichment.description
    price = _number_value(_value(row, mapping, 'preco'))
    if price is not None and price >= 0:
        payload['preco'] = price
    brand = _clean_text(_value(row, mapping, 'marca'), 60)
    if brand and not brand.lower().startswith(('mega center', 'stoqui')):
        payload['marca'] = brand
    ncm = _digits_only(_value(row, mapping, 'ncm'))
    if len(ncm) == 8:
        payload['tributacao'] = {'ncm': ncm}
    meta = {
        'category': enrichment.category,
        'images': list(enrichment.image_urls),
        'confidence': enrichment.confidence,
        'warnings': list(enrichment.warnings),
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
        full['midia'] = {'imagens': [{'link': url} for url in images]}

    with_category = dict(base)
    if category_id:
        with_category['categoria'] = {'id': category_id}
    elif category:
        with_category['categoria'] = {'descricao': category}

    variants: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    seen: set[str] = set()
    for label, payload in (
        ('smart_completo_categoria_imagem', full),
        ('smart_categoria_sem_imagem', with_category),
        ('smart_minimo_sem_categoria_imagem', base),
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
    token, _meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return _safe_preview_payloads(df, OP_CADASTRO, limit=limit)
    mapping = _column_map(df.columns)
    out: list[dict[str, Any]] = []
    for _index, row in df.fillna('').head(limit).iterrows():
        variants = _payload_variants(token, row, mapping)
        if variants:
            label, payload, meta = variants[0]
            out.append({'payload': payload, 'status': 'OK', 'motivo': f'BLINGSMARTCORE {label} · confiança {meta.get("confidence", 0)}/100'})
        else:
            out.append({'payload': {}, 'status': 'IGNORADO', 'motivo': 'Nome/código insuficiente para cadastro.'})
    return out


def preview_payloads(df: pd.DataFrame, operation: str, *, limit: int = 5) -> list[dict[str, Any]]:
    normalized = normalize_operation(operation)
    if normalized == OP_CADASTRO:
        return _smart_preview_payloads(df, limit=limit)
    return _safe_preview_payloads(df, operation, limit=limit)


def _emit_progress(callback: Callable[[dict[str, Any]], None] | None, payload: dict[str, Any]) -> None:
    if not callback:
        return
    try:
        callback(payload)
    except Exception:
        pass


def _send_cadastro_smart(df: pd.DataFrame, *, limit: int | None = None, progress_callback: Callable[[dict[str, Any]], None] | None = None) -> DirectSendResult:
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
            _emit_progress(progress_callback, {'stage': 'Cadastrando no Bling', 'processed': position, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': position / max(total, 1)})
            continue

        ok = False
        attempts: list[dict[str, Any]] = []
        last_response: requests.Response | None = None
        for strategy, payload, meta in variants:
            try:
                response = requests.post(_url(create_path), headers=_headers(token), json=payload, timeout=SEND_TIMEOUT)
                last_response = response
                attempts.append({'strategy': strategy, 'status': int(response.status_code), 'confidence': meta.get('confidence'), 'category': meta.get('category'), 'category_id': meta.get('category_id'), 'warnings': meta.get('warnings'), 'response_preview': str(response.text or '')[:300]})
                if response.status_code < 400:
                    ok = True
                    add_audit_event('bling_smart_cadastro_strategy_succeeded', area='BLING_ENVIO', status='OK', details={'line': line, 'strategy': strategy, 'meta': meta, 'responsible_file': RESPONSIBLE_FILE})
                    break
                if response.status_code in {401, 403}:
                    break
            except Exception as exc:
                attempts.append({'strategy': strategy, 'status': 'EXCEPTION', 'error': str(exc)[:240]})
                continue

        if ok:
            sent += 1
        else:
            failed += 1
            status = getattr(last_response, 'status_code', 'sem resposta')
            preview = str(getattr(last_response, 'text', '') or '')[:500]
            if len(errors) < 8:
                errors.append(f'Linha {line}: Bling recusou cadastro inteligente ({status}) após {len(variants)} tentativa(s). {preview}')
            add_audit_event('bling_smart_cadastro_failed', area='BLING_ENVIO', status='AVISO', details={'line': line, 'status': status, 'attempts': attempts[-5:], 'responsible_file': RESPONSIBLE_FILE})
        _emit_progress(progress_callback, {'stage': 'Cadastrando no Bling', 'processed': position, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': position / max(total, 1)})

    _emit_progress(progress_callback, {'stage': 'Cadastro inteligente concluído', 'processed': total, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': 1.0})
    add_audit_event('bling_smart_cadastro_finished', area='BLING_ENVIO', status='OK' if failed == 0 else 'PARCIAL', details={'attempted': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'mode': 'heuristic_category_image_fallback', 'responsible_file': RESPONSIBLE_FILE})
    return DirectSendResult(total, sent, failed, skipped, tuple(errors), tuple())


def send_dataframe_to_bling(
    df: pd.DataFrame,
    operation: str,
    *,
    limit: int | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> DirectSendResult:
    normalized = normalize_operation(operation)
    if normalized == OP_CADASTRO:
        return _send_cadastro_smart(df, limit=limit, progress_callback=progress_callback)
    return _safe_send_dataframe_to_bling(df, operation, limit=limit, progress_callback=progress_callback)


__all__ = ['DirectSendResult', 'is_direct_send_available', 'preview_payloads', 'send_dataframe_to_bling']
