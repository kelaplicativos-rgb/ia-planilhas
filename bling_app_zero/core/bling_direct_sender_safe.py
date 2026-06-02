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
    send_dataframe_to_bling as _send_dataframe_to_bling,
)
from bling_app_zero.core.bling_token_store import load_token
from bling_app_zero.core.operation_contract import OP_ESTOQUE, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_direct_sender_safe.py'
DEFAULT_API_BASE_URL = 'https://www.bling.com.br/Api/v3'
API_STOCK_DEPOSIT_KEY = 'bling_api_stock_deposit_name'
API_STOCK_DEPOSIT_ID_KEY = 'bling_api_stock_deposit_id'
API_STOCK_DEPOSIT_OPTIONS_KEY = 'bling_api_stock_deposit_options'
PRODUCT_ID_COLUMN = 'id produto bling'
PRODUCT_RESOLUTION_CACHE_KEY = 'bling_safe_product_resolution_cache_v2'

COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    'id': ('id produto bling', 'id_produto_bling', 'id bling', 'id_bling', 'codigo bling', 'código bling', 'id produto', 'id_produto', 'idproduto', 'id'),
    'codigo': ('código', 'codigo', 'sku', 'ref', 'referencia', 'referência', 'codigo produto', 'código produto', 'cod produto', 'cod'),
    'gtin': ('gtin', 'ean', 'codigo de barras', 'código de barras', 'gtin/ean'),
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


def _normalize_column_name(value: object) -> str:
    text = str(value or '').strip().lower()
    text = text.replace('ã', 'a').replace('á', 'a').replace('à', 'a').replace('â', 'a')
    text = text.replace('é', 'e').replace('ê', 'e')
    text = text.replace('í', 'i')
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


def _headers(token: dict[str, Any]) -> dict[str, str]:
    return {'Accept': 'application/json', 'Content-Type': 'application/json', 'Authorization': f"Bearer {token.get('access_token')}"}


def _lookup_path() -> str:
    return _secret('product_lookup_path', '/produtos') or '/produtos'


def _deposit_paths() -> list[str]:
    configured = _secret('stock_deposits_path', '')
    paths = [configured] if configured else []
    paths.extend(['/estoques/depositos', '/depositos', '/estoque/depositos'])
    out: list[str] = []
    for path in paths:
        value = str(path or '').strip()
        if value and value not in out:
            out.append(value)
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
        item.get('codigo'),
        item.get('sku'),
        item.get('codigoProduto'),
        item.get('gtin'),
        item.get('ean'),
        item.get('codigoBarras'),
        tributacao.get('gtin'),
        tributacao.get('ean'),
        tributacao.get('codigoBarras'),
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

    params_list = ({'codigo': candidate}, {'criterio': candidate}, {'pesquisa': candidate})
    for params in params_list:
        try:
            response = requests.get(_url(_lookup_path()), headers=_headers(token), params=params, timeout=20)
            if response.status_code >= 400:
                continue
            items = _extract_items(response.json())
            exact_matches: list[tuple[str, dict[str, Any]]] = []
            loose_matches: list[tuple[str, dict[str, Any]]] = []
            for item in items:
                item_id = str(item.get('id') or item.get('idProduto') or '').strip()
                if not item_id:
                    continue
                identifiers = _item_identifiers(item)
                if any(identifier.lower() == key for identifier in identifiers):
                    exact_matches.append((item_id, item))
                elif len(items) == 1:
                    loose_matches.append((item_id, item))
            match = exact_matches[0] if exact_matches else (loose_matches[0] if loose_matches else None)
            if match:
                item_id, item = match
                cache[key] = item_id
                add_audit_event(
                    'bling_safe_product_resolved_before_send',
                    area='BLING_ENVIO',
                    status='OK',
                    details={'candidate': candidate, 'product_id': item_id, 'params': params, 'identifiers': _item_identifiers(item), 'responsible_file': RESPONSIBLE_FILE},
                )
                return item_id
        except Exception as exc:
            add_audit_event('bling_safe_product_lookup_exception', area='BLING_ENVIO', status='AVISO', details={'candidate': candidate, 'error': str(exc), 'responsible_file': RESPONSIBLE_FILE})
            break
    cache[key] = ''
    return ''


def _row_candidates(row: pd.Series, mapping: dict[str, str]) -> list[str]:
    return _unique_non_empty([_value(row, mapping, 'codigo'), _value(row, mapping, 'gtin'), _value(row, mapping, 'id')])


def _prepare_stock_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    token, _meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return df

    out = df.copy().fillna('')
    mapping = _column_map(out.columns)
    if PRODUCT_ID_COLUMN not in out.columns:
        out.insert(0, PRODUCT_ID_COLUMN, '')

    resolved = unresolved = 0
    for index, row in out.iterrows():
        existing = str(row.get(PRODUCT_ID_COLUMN) or '').strip()
        if existing:
            resolved += 1
            continue
        product_id = ''
        for candidate in _row_candidates(row, mapping):
            product_id = _resolve_product_by_candidate(token, candidate)
            if product_id:
                break
        if product_id:
            out.at[index, PRODUCT_ID_COLUMN] = product_id
            resolved += 1
        else:
            unresolved += 1
    add_audit_event(
        'bling_safe_stock_dataframe_prepared',
        area='BLING_ENVIO',
        status='OK' if unresolved == 0 else 'PARCIAL',
        details={'rows': int(len(out)), 'resolved': int(resolved), 'unresolved': int(unresolved), 'responsible_file': RESPONSIBLE_FILE},
    )
    return out


def _normalize_deposit(item: dict[str, Any]) -> dict[str, str] | None:
    deposit_id = str(item.get('id') or item.get('idDeposito') or item.get('id_deposito') or item.get('codigo') or '').strip()
    name = str(item.get('descricao') or item.get('nome') or item.get('name') or item.get('description') or '').strip()
    nested = item.get('deposito')
    if isinstance(nested, dict):
        deposit_id = deposit_id or str(nested.get('id') or nested.get('idDeposito') or '').strip()
        name = name or str(nested.get('descricao') or nested.get('nome') or '').strip()
    if not deposit_id and not name:
        return None
    return {'id': deposit_id, 'nome': name, 'label': f'{name} · ID {deposit_id}' if name and deposit_id else name or f'ID {deposit_id}'}


def _load_stock_deposits() -> list[dict[str, str]]:
    cached = st.session_state.get(API_STOCK_DEPOSIT_OPTIONS_KEY)
    if isinstance(cached, list) and cached:
        return [item for item in cached if isinstance(item, dict)]

    token, _meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return []

    headers = {'Accept': 'application/json', 'Authorization': f"Bearer {token.get('access_token')}"}
    errors: list[str] = []
    for path in _deposit_paths():
        try:
            response = requests.get(_url(path), headers=headers, timeout=20)
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
                if key in seen:
                    continue
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


def _ensure_stock_deposit_ready() -> None:
    if str(st.session_state.get(API_STOCK_DEPOSIT_ID_KEY) or '').strip():
        return

    current_name = str(st.session_state.get(API_STOCK_DEPOSIT_KEY) or _secret('stock_deposit_name', _secret('default_stock_deposit_name', '')) or '').strip()
    deposits = _load_stock_deposits()
    if not deposits:
        return

    if current_name:
        wanted = current_name.lower()
        for item in deposits:
            item_id = str(item.get('id') or '').strip()
            item_name = str(item.get('nome') or '').strip()
            if item_id and (wanted == item_name.lower() or wanted == item_id.lower()):
                st.session_state[API_STOCK_DEPOSIT_ID_KEY] = item_id
                st.session_state[API_STOCK_DEPOSIT_KEY] = item_name or current_name
                add_audit_event('bling_safe_stock_deposit_resolved_by_name', area='BLING_ENVIO', status='OK', details={'deposit_id': item_id, 'deposit_name': item_name, 'responsible_file': RESPONSIBLE_FILE})
                return

    if len(deposits) == 1:
        item = deposits[0]
        item_id = str(item.get('id') or '').strip()
        item_name = str(item.get('nome') or '').strip()
        if item_id:
            st.session_state[API_STOCK_DEPOSIT_ID_KEY] = item_id
            st.session_state[API_STOCK_DEPOSIT_KEY] = item_name
            add_audit_event('bling_safe_stock_deposit_auto_selected_single', area='BLING_ENVIO', status='OK', details={'deposit_id': item_id, 'deposit_name': item_name, 'responsible_file': RESPONSIBLE_FILE})


def _product_not_found_line_numbers(errors: tuple[str, ...]) -> set[int]:
    lines: set[int] = set()
    for error in errors:
        text = str(error or '')
        low = text.lower()
        if 'produto não encontrado' not in low and 'produto nao encontrado' not in low:
            continue
        match = re.search(r'linha\s+(\d+)', low)
        if not match:
            continue
        try:
            lines.add(int(match.group(1)))
        except Exception:
            pass
    return lines


def _only_product_not_found_indices(result: DirectSendResult) -> tuple[int, ...]:
    if not result.not_found_indices:
        return ()
    product_lines = _product_not_found_line_numbers(result.errors)
    if not product_lines:
        return ()
    fixed: list[int] = []
    for index in result.not_found_indices:
        try:
            line_number = int(index) + 1
        except Exception:
            continue
        if line_number in product_lines:
            fixed.append(int(index))
    return tuple(fixed)


def preview_payloads(df: pd.DataFrame, operation: str, *, limit: int = 5) -> list[dict[str, Any]]:
    normalized = normalize_operation(operation)
    prepared = _prepare_stock_dataframe(df) if normalized == OP_ESTOQUE else df
    return _raw_preview_payloads(prepared, operation, limit=limit)


def send_dataframe_to_bling(
    df: pd.DataFrame,
    operation: str,
    *,
    limit: int | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> DirectSendResult:
    normalized = normalize_operation(operation)
    prepared = df
    if normalized == OP_ESTOQUE:
        _ensure_stock_deposit_ready()
        prepared = _prepare_stock_dataframe(df)

    result = _send_dataframe_to_bling(prepared, operation, limit=limit, progress_callback=progress_callback)
    if normalized != OP_ESTOQUE or not result.not_found_indices:
        return result

    fixed_not_found = _only_product_not_found_indices(result)
    if fixed_not_found == result.not_found_indices:
        return result

    add_audit_event(
        'bling_safe_not_found_reclassified',
        area='BLING_ENVIO',
        status='CORRIGIDO',
        details={
            'original_not_found_count': len(result.not_found_indices),
            'new_not_found_count': len(fixed_not_found),
            'reason': 'Falha não era produto não encontrado; pode ser depósito, endpoint, payload ou permissão.',
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return DirectSendResult(
        attempted=result.attempted,
        sent=result.sent,
        failed=result.failed,
        skipped=result.skipped,
        errors=result.errors,
        not_found_indices=fixed_not_found,
    )


__all__ = ['DirectSendResult', 'is_direct_send_available', 'preview_payloads', 'send_dataframe_to_bling']
