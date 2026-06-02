from __future__ import annotations

import re
from typing import Any, Callable

import pandas as pd
import requests
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_direct_sender import (
    DirectSendResult,
    is_direct_send_available,
    preview_payloads,
    send_dataframe_to_bling as _send_dataframe_to_bling,
)
from bling_app_zero.core.bling_token_store import load_token
from bling_app_zero.core.operation_contract import OP_ESTOQUE, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_direct_sender_safe.py'
DEFAULT_API_BASE_URL = 'https://www.bling.com.br/Api/v3'
API_STOCK_DEPOSIT_KEY = 'bling_api_stock_deposit_name'
API_STOCK_DEPOSIT_ID_KEY = 'bling_api_stock_deposit_id'
API_STOCK_DEPOSIT_OPTIONS_KEY = 'bling_api_stock_deposit_options'


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


def send_dataframe_to_bling(
    df: pd.DataFrame,
    operation: str,
    *,
    limit: int | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> DirectSendResult:
    normalized = normalize_operation(operation)
    if normalized == OP_ESTOQUE:
        _ensure_stock_deposit_ready()

    result = _send_dataframe_to_bling(df, operation, limit=limit, progress_callback=progress_callback)
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
