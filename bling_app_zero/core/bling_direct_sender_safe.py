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
from bling_app_zero.core.operation_contract import OP_ESTOQUE, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_direct_sender_safe.py'
DEFAULT_API_BASE_URL = 'https://www.bling.com.br/Api/v3'
API_STOCK_DEPOSIT_KEY = 'bling_api_stock_deposit_name'
API_STOCK_DEPOSIT_ID_KEY = 'bling_api_stock_deposit_id'
API_STOCK_DEPOSIT_OPTIONS_KEY = 'bling_api_stock_deposit_options'
PRODUCT_RESOLUTION_CACHE_KEY = 'bling_safe_product_resolution_cache_v7'
PRODUCT_LOOKUP_TIMEOUT = 12
DEPOSIT_LOOKUP_TIMEOUT = 15
SEND_TIMEOUT = 30

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    'id': ('id produto bling', 'id_produto_bling', 'id bling', 'id_bling', 'id produto bling api', 'id produto'),
    'codigo': ('código', 'codigo', 'sku', 'ref', 'referencia', 'referência', 'codigo produto', 'código produto', 'cod produto', 'cod'),
    'gtin': ('gtin', 'ean', 'codigo de barras', 'código de barras', 'gtin/ean'),
    'quantidade': ('quantidade', 'saldo', 'estoque', 'balanço', 'balanco', 'qtd', 'qtde'),
    'deposito': ('depósito', 'deposito', 'nome depósito', 'nome deposito', 'depósito padrão', 'deposito padrao'),
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
    if path.startswith('http://') or path.startswith('https://'):
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


def _api_number(value: float) -> int | float:
    try:
        number = float(value)
        return int(number) if number.is_integer() else number
    except Exception:
        return value


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


def _item_identifiers(item: dict[str, Any]) -> list[str]:
    tributacao = item.get('tributacao') if isinstance(item.get('tributacao'), dict) else {}
    return _unique_non_empty([
        item.get('codigo'), item.get('sku'), item.get('codigoProduto'),
        item.get('gtin'), item.get('ean'), item.get('codigoBarras'),
        tributacao.get('gtin'), tributacao.get('ean'), tributacao.get('codigoBarras'),
    ])


def _resolution_cache() -> dict[str, str]:
    cache = st.session_state.get(PRODUCT_RESOLUTION_CACHE_KEY)
    if not isinstance(cache, dict):
        cache = {}
        st.session_state[PRODUCT_RESOLUTION_CACHE_KEY] = cache
    return cache


def _resolve_product_by_candidate(token: dict[str, Any], candidate: str) -> str:
    candidate = str(candidate or '').strip()
    if not candidate:
        return ''
    cache = _resolution_cache()
    key = candidate.lower()
    if key in cache:
        return str(cache.get(key) or '')

    lookup_path = _secret('product_lookup_path', '/produtos') or '/produtos'
    for params in ({'codigo': candidate}, {'criterio': candidate}, {'pesquisa': candidate}):
        try:
            response = requests.get(_url(lookup_path), headers=_headers(token), params=params, timeout=PRODUCT_LOOKUP_TIMEOUT)
            if response.status_code >= 400:
                continue
            items = _extract_items(response.json())
            exact: list[tuple[str, dict[str, Any]]] = []
            loose: list[tuple[str, dict[str, Any]]] = []
            for item in items:
                item_id = str(item.get('id') or item.get('idProduto') or '').strip()
                if not item_id:
                    continue
                ids = _item_identifiers(item)
                if any(identifier.lower() == key for identifier in ids):
                    exact.append((item_id, item))
                elif len(items) == 1:
                    loose.append((item_id, item))
            match = exact[0] if exact else (loose[0] if loose else None)
            if match:
                item_id, item = match
                cache[key] = item_id
                add_audit_event('bling_safe_product_resolved_before_send', area='BLING_ENVIO', status='OK', details={'candidate': candidate, 'product_id': item_id, 'params': params, 'responsible_file': RESPONSIBLE_FILE})
                return item_id
        except Exception as exc:
            add_audit_event('bling_safe_product_lookup_exception', area='BLING_ENVIO', status='AVISO', details={'candidate': candidate, 'error': str(exc), 'responsible_file': RESPONSIBLE_FILE})
            break
    cache[key] = ''
    return ''


def _row_candidates(row: pd.Series, mapping: dict[str, str]) -> list[str]:
    return _unique_non_empty([_value(row, mapping, 'id'), _value(row, mapping, 'codigo'), _value(row, mapping, 'gtin')])


def _normalize_deposit(item: dict[str, Any]) -> dict[str, str] | None:
    deposit_id = str(item.get('id') or item.get('idDeposito') or item.get('id_deposito') or item.get('codigo') or '').strip()
    name = str(item.get('descricao') or item.get('nome') or item.get('name') or item.get('description') or '').strip()
    nested = item.get('deposito')
    if isinstance(nested, dict):
        deposit_id = deposit_id or str(nested.get('id') or nested.get('idDeposito') or '').strip()
        name = name or str(nested.get('descricao') or nested.get('nome') or '').strip()
    if not deposit_id and not name:
        return None
    return {'id': deposit_id, 'nome': name}


def _load_stock_deposits(token: dict[str, Any]) -> list[dict[str, str]]:
    cached = st.session_state.get(API_STOCK_DEPOSIT_OPTIONS_KEY)
    if isinstance(cached, list) and cached:
        return [item for item in cached if isinstance(item, dict)]
    paths = [_secret('stock_deposits_path', ''), '/estoques/depositos', '/depositos', '/estoque/depositos']
    errors: list[str] = []
    seen_paths: set[str] = set()
    for path in [str(p or '').strip() for p in paths if str(p or '').strip()]:
        if path in seen_paths:
            continue
        seen_paths.add(path)
        try:
            response = requests.get(_url(path), headers={'Accept': 'application/json', 'Authorization': f"Bearer {token.get('access_token')}"}, timeout=DEPOSIT_LOOKUP_TIMEOUT)
            if response.status_code >= 400:
                errors.append(f'{path}: HTTP {response.status_code}')
                continue
            deposits: list[dict[str, str]] = []
            seen: set[tuple[str, str]] = set()
            for item in _extract_items(response.json()):
                deposit = _normalize_deposit(item)
                if not deposit:
                    continue
                key = (deposit.get('id', ''), deposit.get('nome', ''))
                if key not in seen:
                    seen.add(key)
                    deposits.append(deposit)
            if deposits:
                st.session_state[API_STOCK_DEPOSIT_OPTIONS_KEY] = deposits
                add_audit_event('bling_safe_stock_deposits_loaded', area='BLING_ENVIO', status='OK', details={'path': path, 'count': len(deposits), 'responsible_file': RESPONSIBLE_FILE})
                return deposits
        except Exception as exc:
            errors.append(f'{path}: {exc}')
    add_audit_event('bling_safe_stock_deposits_load_failed', area='BLING_ENVIO', status='AVISO', details={'errors': errors[:4], 'responsible_file': RESPONSIBLE_FILE})
    return []


def _resolve_deposit_id(token: dict[str, Any], preferred_name: str = '') -> str:
    current_id = str(st.session_state.get(API_STOCK_DEPOSIT_ID_KEY) or _secret('stock_deposit_id', '') or '').strip()
    if current_id:
        return current_id
    wanted = str(preferred_name or st.session_state.get(API_STOCK_DEPOSIT_KEY) or _secret('stock_deposit_name', _secret('default_stock_deposit_name', '')) or '').strip().lower()
    deposits = _load_stock_deposits(token)
    if wanted:
        for item in deposits:
            item_id = str(item.get('id') or '').strip()
            item_name = str(item.get('nome') or '').strip().lower()
            if item_id and (wanted == item_name or wanted == item_id.lower()):
                st.session_state[API_STOCK_DEPOSIT_ID_KEY] = item_id
                return item_id
    if len(deposits) == 1 and str(deposits[0].get('id') or '').strip():
        item_id = str(deposits[0].get('id') or '').strip()
        st.session_state[API_STOCK_DEPOSIT_ID_KEY] = item_id
        return item_id
    return ''


def _stock_payload(product_id: str, deposit_id: str, quantity: float) -> dict[str, Any]:
    return {
        'produto': {'id': str(product_id)},
        'deposito': {'id': str(deposit_id)},
        'operacao': 'B',
        'quantidade': _api_number(quantity),
    }


def _stock_endpoint_attempts(product_id: str) -> list[tuple[str, str]]:
    configured_path = _secret('stock_write_path', '/estoques') or '/estoques'
    configured_method = (_secret('stock_update_method', 'POST') or 'POST').upper()
    raw = [
        (configured_method, configured_path),
        ('POST', '/estoques'),
        ('POST', '/estoques/saldos'),
        ('PUT', f'/estoques/saldos/{product_id}'),
        ('PATCH', f'/estoques/saldos/{product_id}'),
    ]
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for method, path in raw:
        path = str(path or '').replace('{id}', product_id).replace('{idProduto}', product_id)
        key = (method, path)
        if path and '{' not in path and key not in seen:
            out.append(key)
            seen.add(key)
    return out


def _emit_progress(callback: Callable[[dict[str, Any]], None] | None, payload: dict[str, Any]) -> None:
    if not callback:
        return
    try:
        callback(payload)
    except Exception:
        pass


def _stock_preview_payloads(df: pd.DataFrame, *, limit: int = 5) -> list[dict[str, Any]]:
    token, _meta = load_token()
    mapping = _column_map(df.columns)
    previews: list[dict[str, Any]] = []
    if not isinstance(token, dict) or not token.get('access_token'):
        return [{'payload': {}, 'status': 'IGNORADO', 'motivo': 'Bling não conectado.'}]
    deposit_id = _resolve_deposit_id(token)
    for _index, row in df.fillna('').head(limit).iterrows():
        qty = _number_value(_value(row, mapping, 'quantidade'))
        product_id = ''
        for candidate in _row_candidates(row, mapping):
            product_id = _resolve_product_by_candidate(token, candidate)
            if product_id:
                break
        if not product_id:
            previews.append({'payload': {}, 'status': 'IGNORADO', 'motivo': 'Produto não resolvido no Bling por Código/GTIN/ID.'})
        elif not deposit_id:
            previews.append({'payload': {}, 'status': 'IGNORADO', 'motivo': 'Depósito não resolvido no Bling.'})
        elif qty is None:
            previews.append({'payload': {}, 'status': 'IGNORADO', 'motivo': 'Quantidade/saldo inválido.'})
        else:
            previews.append({'payload': _stock_payload(product_id, deposit_id, qty), 'status': 'OK', 'motivo': ''})
    return previews


def preview_payloads(df: pd.DataFrame, operation: str, *, limit: int = 5) -> list[dict[str, Any]]:
    normalized = normalize_operation(operation)
    if normalized == OP_ESTOQUE:
        return _stock_preview_payloads(df, limit=limit)
    return _raw_preview_payloads(df, operation, limit=limit)


def _send_stock_dataframe_to_bling(df: pd.DataFrame, *, limit: int | None = None, progress_callback: Callable[[dict[str, Any]], None] | None = None) -> DirectSendResult:
    token, _meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return DirectSendResult(0, 0, 0, len(df) if isinstance(df, pd.DataFrame) else 0, ('Bling não conectado. Conecte o app antes de enviar direto.',))
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
        qty = _number_value(_value(row, mapping, 'quantidade'))
        if qty is None:
            skipped += 1
            if len(errors) < 8:
                errors.append(f'Linha {line}: quantidade/saldo ausente ou inválido.')
            _emit_progress(progress_callback, {'stage': 'Enviando ao Bling', 'processed': position, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': position / max(total, 1)})
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
                errors.append(f'Linha {line}: produto não encontrado no Bling por Código/SKU/GTIN/ID.')
            _emit_progress(progress_callback, {'stage': 'Enviando ao Bling', 'processed': position, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': position / max(total, 1)})
            continue

        deposit_id = _resolve_deposit_id(token, _value(row, mapping, 'deposito')) or default_deposit_id
        if not deposit_id:
            failed += 1
            if len(errors) < 8:
                errors.append(f'Linha {line}: depósito não resolvido no Bling.')
            _emit_progress(progress_callback, {'stage': 'Enviando ao Bling', 'processed': position, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': position / max(total, 1)})
            continue

        payload = _stock_payload(product_id, deposit_id, qty)
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
            if len(errors) < 8:
                errors.append(f'Linha {line}: Bling recusou estoque ({status}). Primeiro endpoint tentado: /estoques. {preview}')
            add_audit_event('bling_safe_stock_clean_payload_failed', area='BLING_ENVIO', status='AVISO', details={'line': line, 'product_id': product_id, 'deposit_id': deposit_id, 'quantity': qty, 'payload': payload, 'attempts': attempts[-6:], 'responsible_file': RESPONSIBLE_FILE})
        _emit_progress(progress_callback, {'stage': 'Enviando ao Bling', 'processed': position, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': position / max(total, 1)})

    result = DirectSendResult(total, sent, failed, skipped, tuple(errors), tuple(not_found))
    _emit_progress(progress_callback, {'stage': 'Envio concluído', 'processed': total, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': 1.0})
    add_audit_event('bling_safe_stock_clean_send_finished', area='BLING_ENVIO', status='OK' if failed == 0 else 'PARCIAL', details={'attempted': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'not_found_count': len(not_found), 'responsible_file': RESPONSIBLE_FILE})
    return result


def send_dataframe_to_bling(
    df: pd.DataFrame,
    operation: str,
    *,
    limit: int | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> DirectSendResult:
    normalized = normalize_operation(operation)
    if normalized == OP_ESTOQUE:
        return _send_stock_dataframe_to_bling(df, limit=limit, progress_callback=progress_callback)
    return _raw_send_dataframe_to_bling(df, operation, limit=limit, progress_callback=progress_callback)


__all__ = ['DirectSendResult', 'is_direct_send_available', 'preview_payloads', 'send_dataframe_to_bling']
