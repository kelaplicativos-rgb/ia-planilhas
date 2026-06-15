from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable

import pandas as pd
import requests
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_token_store import load_token
from bling_app_zero.core.operation_contract import OP_ATUALIZACAO_PRECO, OP_CADASTRO, OP_ESTOQUE, normalize_operation, operation_label
from bling_app_zero.core.operation_safety_guard import require_rows_before_api

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_direct_sender.py'
DEFAULT_API_BASE_URL = 'https://www.bling.com.br/Api/v3'
SAFE_DELEGATED_OPERATIONS = {OP_CADASTRO, OP_ESTOQUE}
PRICE_LOOKUP_TIMEOUT = 12
PRICE_SEND_TIMEOUT = 30

PRICE_COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    'id': ('id', 'id produto', 'id_produto', 'id produto bling', 'id_produto_bling', 'id bling', 'id_bling', 'codigo bling', 'código bling', 'id produto api'),
    'codigo': ('código', 'codigo', 'sku', 'ref', 'referencia', 'referência', 'codigo produto', 'código produto', 'cod', 'cód'),
    'gtin': ('gtin', 'ean', 'codigo de barras', 'código de barras', 'gtin/ean'),
    'preco': ('preço', 'preco', 'preço unitário', 'preco unitario', 'preço unitário (obrigatório)', 'preco unitario (obrigatorio)', 'valor', 'valor venda', 'preço de venda', 'preco de venda'),
    'price_target': ('bling preço destino', 'bling preco destino', 'preço destino', 'preco destino'),
    'channel_id': ('bling canal venda id', 'canal venda id', 'id canal', 'id loja', 'loja id'),
    'channel_name': ('bling canal venda nome', 'canal venda nome', 'nome canal', 'nome loja'),
}


@dataclass(frozen=True)
class DirectSendResult:
    attempted: int
    sent: int
    failed: int
    skipped: int
    errors: tuple[str, ...]
    not_found_indices: tuple[int, ...] = ()


def _secret(name: str, default: str = '') -> str:
    try:
        bling = st.secrets.get('bling', {})
        value = bling.get(name, default) if hasattr(bling, 'get') else default
        return str(value or default).strip()
    except Exception:
        return default


def api_base_url() -> str:
    return (_secret('api_base_url', DEFAULT_API_BASE_URL) or DEFAULT_API_BASE_URL).rstrip('/')


def _url(path: str) -> str:
    if str(path or '').startswith(('http://', 'https://')):
        return str(path)
    return api_base_url() + '/' + str(path or '').lstrip('/')


def _token() -> tuple[dict[str, Any] | None, str]:
    token, meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return None, str(meta.get('store_mode') or '')
    return token, str(meta.get('store_mode') or '')


def _headers(token: dict[str, Any]) -> dict[str, str]:
    return {'Accept': 'application/json', 'Content-Type': 'application/json', 'Authorization': f"Bearer {token.get('access_token')}"}


def is_direct_send_available() -> bool:
    token, _mode = _token()
    return isinstance(token, dict) and bool(token.get('access_token'))


def _norm(value: object) -> str:
    text = str(value or '').strip().lower()
    for old, new in {'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c'}.items():
        text = text.replace(old, new)
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', text)).strip()


def _column_map(columns: Iterable[object]) -> dict[str, str]:
    normalized = {_norm(column): str(column) for column in columns}
    out: dict[str, str] = {}
    for field, aliases in PRICE_COLUMN_ALIASES.items():
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
    return [payload] if payload.get('id') or payload.get('idProduto') else []


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


def _session_cache(key: str) -> dict[str, str]:
    cache = st.session_state.get(key)
    if not isinstance(cache, dict):
        cache = {}
        st.session_state[key] = cache
    return cache


def _resolve_product_by_candidate(token: dict[str, Any], candidate: str) -> str:
    candidate = str(candidate or '').strip()
    if not candidate:
        return ''
    cache = _session_cache('bling_direct_price_product_resolution_cache_v1')
    key = candidate.lower()
    if key in cache:
        return str(cache.get(key) or '')

    if candidate.isdigit() and len(candidate) >= 6:
        try:
            response = requests.get(_url(f'/produtos/{candidate}'), headers=_headers(token), timeout=PRICE_LOOKUP_TIMEOUT)
            if response.status_code < 400:
                data = response.json() if str(response.text or '').strip() else {}
                items = _extract_items(data)
                item = items[0] if items else data if isinstance(data, dict) else {}
                item_id = str(item.get('id') or item.get('idProduto') or candidate).strip()
                if item_id:
                    cache[key] = item_id
                    return item_id
        except Exception as exc:
            add_audit_event('bling_price_product_direct_id_lookup_exception', area='BLING_ENVIO', status='AVISO', details={'candidate': candidate, 'error': str(exc)[:180], 'responsible_file': RESPONSIBLE_FILE})

    lookup_path = _secret('product_lookup_path', '/produtos') or '/produtos'
    for params in ({'codigo': candidate}, {'criterio': candidate}, {'pesquisa': candidate}):
        try:
            response = requests.get(_url(lookup_path), headers=_headers(token), params=params, timeout=PRICE_LOOKUP_TIMEOUT)
            if response.status_code >= 400:
                continue
            items = _extract_items(response.json())
            for item in items:
                item_id = str(item.get('id') or item.get('idProduto') or '').strip()
                identifiers = [item_identifier.lower() for item_identifier in _item_identifiers(item)]
                if item_id and (candidate.lower() in identifiers or len(items) == 1):
                    cache[key] = item_id
                    return item_id
        except Exception as exc:
            add_audit_event('bling_price_product_lookup_exception', area='BLING_ENVIO', status='AVISO', details={'candidate': candidate, 'error': str(exc)[:180], 'responsible_file': RESPONSIBLE_FILE})
            break
    cache[key] = ''
    return ''


def _row_candidates(row: pd.Series, mapping: dict[str, str]) -> list[str]:
    return _unique_non_empty([_value(row, mapping, 'id'), _value(row, mapping, 'codigo'), _value(row, mapping, 'gtin')])


def _price_payloads(product_id: str, price: float, channel_id: str = '') -> list[tuple[str, str, str, dict[str, Any]]]:
    price_value = _api_number(price)
    configured_path = _secret('price_update_path', '')
    configured_method = (_secret('price_update_method', 'PATCH') or 'PATCH').upper()
    attempts: list[tuple[str, str, str, dict[str, Any]]] = []

    if channel_id:
        channel_payloads = [
            ('canal_payload_produto_loja_preco', {'produto': {'id': str(product_id)}, 'loja': {'id': str(channel_id)}, 'preco': price_value}),
            ('canal_payload_id_produto_id_loja', {'idProduto': str(product_id), 'idLoja': str(channel_id), 'preco': price_value}),
            ('canal_payload_preco_loja', {'preco': price_value, 'loja': {'id': str(channel_id)}}),
        ]
        channel_paths = _unique_non_empty([
            configured_path,
            f'/produtos/{product_id}/precos',
            f'/produtos/{product_id}/lojas/{channel_id}',
            f'/produtos/{product_id}/precos/{channel_id}',
            '/produtos/precos',
        ])
        for path in channel_paths:
            for label, payload in channel_payloads:
                attempts.append((configured_method if path == configured_path else 'POST', path, label, payload))
                attempts.append(('PATCH', path, label, payload))
                attempts.append(('PUT', path, label, payload))
        return _dedupe_price_attempts(attempts)

    general_payloads = [
        ('geral_payload_preco', {'preco': price_value}),
        ('geral_payload_produto_preco', {'produto': {'id': str(product_id)}, 'preco': price_value}),
    ]
    general_paths = _unique_non_empty([configured_path, f'/produtos/{product_id}'])
    for path in general_paths:
        for label, payload in general_payloads:
            attempts.append((configured_method if path == configured_path else 'PATCH', path, label, payload))
            attempts.append(('PUT', path, label, payload))
            attempts.append(('PATCH', path, label, payload))
    return _dedupe_price_attempts(attempts)


def _dedupe_price_attempts(attempts: list[tuple[str, str, str, dict[str, Any]]]) -> list[tuple[str, str, str, dict[str, Any]]]:
    out: list[tuple[str, str, str, dict[str, Any]]] = []
    seen: set[str] = set()
    for method, path, label, payload in attempts:
        method = str(method or 'PATCH').upper()
        path = str(path or '').replace('{id}', '').replace('{idProduto}', '').strip()
        if not path or '{' in path:
            continue
        key = f'{method}|{path}|{label}|{payload}'
        if key not in seen:
            out.append((method, path, label, payload))
            seen.add(key)
    return out


def _emit_progress(progress_callback: Callable[[dict[str, Any]], None] | None, payload: dict[str, Any]) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(payload)
    except Exception:
        pass


def _blocked_empty_result(operation: str, progress_callback: Callable[[dict[str, Any]], None] | None = None) -> DirectSendResult:
    normalized = normalize_operation(operation)
    decision = require_rows_before_api(operation=normalized)
    message = decision.message or 'Envio ao Bling bloqueado: sender bruto recebeu origem vazia.'
    _emit_progress(
        progress_callback,
        {'stage': 'Envio bloqueado antes da API', 'operation': normalized, 'processed': 0, 'total': 0, 'sent': 0, 'failed': 0, 'skipped': 0, 'progress': 1.0, 'blocked_before_api': True, 'reason': decision.reason or 'sem_linhas'},
    )
    add_audit_event('bling_direct_sender_blocked_empty_before_api', area='BLING_ENVIO', status='BLOQUEADO', details={'operation': normalized, 'message': message, 'reason': decision.reason or 'sem_linhas', 'decision_details': decision.details or {}, 'responsible_file': RESPONSIBLE_FILE})
    return DirectSendResult(0, 0, 0, 0, (message,), tuple())


def _price_preview_payloads(df: pd.DataFrame, *, limit: int = 5) -> list[dict[str, Any]]:
    mapping = _column_map(df.columns)
    previews: list[dict[str, Any]] = []
    for _index, row in df.fillna('').head(limit).iterrows():
        price = _number_value(_value(row, mapping, 'preco'))
        channel_id = _value(row, mapping, 'channel_id')
        target = _value(row, mapping, 'price_target') or ('Canal de venda' if channel_id else 'Preço geral')
        payload = {'preco': _api_number(price)} if price is not None else {}
        if channel_id:
            payload['loja'] = {'id': channel_id}
        previews.append({'payload': payload, 'status': 'OK' if payload else 'IGNORADO', 'motivo': f'Destino: {target}' if payload else 'Preço ausente ou inválido.'})
    return previews


def preview_payloads(df: pd.DataFrame, operation: str, *, limit: int = 5) -> list[dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    normalized = normalize_operation(operation)
    if normalized in SAFE_DELEGATED_OPERATIONS:
        try:
            from bling_app_zero.core.bling_direct_sender_safe import preview_payloads as _safe_preview_payloads

            return _safe_preview_payloads(df, normalized, limit=limit)
        except Exception as exc:
            add_audit_event('bling_direct_sender_preview_safe_delegate_failed', area='BLING_ENVIO', status='AVISO', details={'operation': normalized, 'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE})
    if normalized == OP_ATUALIZACAO_PRECO:
        return _price_preview_payloads(df, limit=limit)
    previews: list[dict[str, Any]] = []
    for _index, row in df.fillna('').head(limit).iterrows():
        payload = {str(column): row.get(column, '') for column in df.columns if str(row.get(column, '')).strip()}
        previews.append({'payload': payload, 'status': 'OK' if payload else 'IGNORADO', 'motivo': '' if payload else 'Linha vazia.'})
    return previews


def _send_price_dataframe_to_bling(df: pd.DataFrame, *, limit: int | None = None, progress_callback: Callable[[dict[str, Any]], None] | None = None) -> DirectSendResult:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return _blocked_empty_result(OP_ATUALIZACAO_PRECO, progress_callback)
    token, _mode = _token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return DirectSendResult(0, 0, 0, len(df), ('Bling não conectado. Conecte o app antes de atualizar preços.',))

    rows = df.fillna('').head(limit) if limit else df.fillna('')
    mapping = _column_map(rows.columns)
    total = len(rows)
    sent = failed = skipped = 0
    errors: list[str] = []
    not_found: list[int] = []
    _emit_progress(progress_callback, {'stage': 'Iniciando atualização de preços', 'operation': OP_ATUALIZACAO_PRECO, 'processed': 0, 'total': total, 'sent': 0, 'failed': 0, 'skipped': 0, 'progress': 0.0})

    for position, (index, row) in enumerate(rows.iterrows(), start=1):
        line = int(index) + 1 if isinstance(index, int) else position
        price = _number_value(_value(row, mapping, 'preco'))
        if price is None or price < 0:
            skipped += 1
            if len(errors) < 8:
                errors.append(f'Linha {line}: preço ausente ou inválido.')
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

        channel_id = _value(row, mapping, 'channel_id')
        target = _value(row, mapping, 'price_target')
        if 'canal' in _norm(target) and not channel_id:
            failed += 1
            if len(errors) < 8:
                errors.append(f'Linha {line}: canal/loja selecionado sem ID do canal.')
            continue

        ok = False
        last_response: requests.Response | None = None
        attempts_log: list[dict[str, Any]] = []
        for method, path, strategy, payload in _price_payloads(product_id, price, channel_id):
            try:
                response = requests.request(method, _url(path), headers=_headers(token), json=payload, timeout=PRICE_SEND_TIMEOUT)
                last_response = response
                attempts_log.append({'method': method, 'path': path, 'strategy': strategy, 'status': response.status_code, 'payload': payload, 'response_preview': str(response.text or '')[:220]})
                if response.status_code < 400:
                    ok = True
                    break
                if response.status_code in {401, 403}:
                    break
            except Exception as exc:
                attempts_log.append({'method': method, 'path': path, 'strategy': strategy, 'status': 'EXCEPTION', 'error': str(exc)[:180]})

        if ok:
            sent += 1
        else:
            failed += 1
            status = getattr(last_response, 'status_code', 'sem resposta')
            preview = str(getattr(last_response, 'text', '') or '')[:300]
            first_endpoint = attempts_log[0].get('path') if attempts_log else '/produtos/{id}'
            if len(errors) < 8:
                errors.append(f'Linha {line}: Bling recusou preço ({status}). Primeiro endpoint: {first_endpoint}. {preview}')
            add_audit_event('bling_direct_price_update_failed', area='BLING_ENVIO', status='AVISO', details={'line': line, 'product_id': product_id, 'price': price, 'channel_id': channel_id, 'attempts': attempts_log[-6:], 'responsible_file': RESPONSIBLE_FILE})
        _emit_progress(progress_callback, {'stage': 'Atualizando preços no Bling', 'operation': OP_ATUALIZACAO_PRECO, 'processed': position, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': position / max(total, 1)})

    _emit_progress(progress_callback, {'stage': 'Atualização de preços concluída', 'operation': OP_ATUALIZACAO_PRECO, 'processed': total, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': 1.0})
    add_audit_event('bling_direct_price_update_finished', area='BLING_ENVIO', status='OK' if failed == 0 else 'PARCIAL', details={'attempted': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'not_found_count': len(not_found), 'responsible_file': RESPONSIBLE_FILE})
    return DirectSendResult(total, sent, failed, skipped, tuple(errors), tuple(not_found))


def send_dataframe_to_bling(
    df: pd.DataFrame,
    operation: str,
    *,
    limit: int | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> DirectSendResult:
    normalized = normalize_operation(operation)
    if not isinstance(df, pd.DataFrame) or df.empty:
        return _blocked_empty_result(normalized, progress_callback)

    if normalized == OP_ATUALIZACAO_PRECO:
        return _send_price_dataframe_to_bling(df, limit=limit, progress_callback=progress_callback)

    if normalized in SAFE_DELEGATED_OPERATIONS:
        try:
            from bling_app_zero.core.bling_direct_sender_safe import send_dataframe_to_bling as _safe_send_dataframe_to_bling

            add_audit_event(
                'bling_direct_sender_delegated_to_safe_sender',
                area='BLING_ENVIO',
                status='OK',
                details={'operation': normalized, 'rows': len(df), 'reason': 'Cadastro e estoque delegados ao sender seguro com guard preventivo.', 'responsible_file': RESPONSIBLE_FILE},
            )
            return _safe_send_dataframe_to_bling(df, normalized, limit=limit, progress_callback=progress_callback)
        except Exception as exc:
            add_audit_event('bling_direct_sender_safe_delegate_failed', area='BLING_ENVIO', status='ERRO', details={'operation': normalized, 'rows': len(df), 'error': str(exc)[:300], 'responsible_file': RESPONSIBLE_FILE})
            return DirectSendResult(len(df), 0, len(df), 0, (f'Falha ao delegar envio seguro ao Bling: {exc}',), tuple())

    message = f'Operação sem envio direto configurado no sender bruto: {operation_label(normalized)}.'
    add_audit_event('bling_direct_sender_unsupported_operation_blocked', area='BLING_ENVIO', status='BLOQUEADO', details={'operation': normalized, 'rows': len(df), 'message': message, 'responsible_file': RESPONSIBLE_FILE})
    return DirectSendResult(len(df), 0, 0, len(df), (message,), tuple())


__all__ = ['DirectSendResult', 'api_base_url', 'is_direct_send_available', 'preview_payloads', 'send_dataframe_to_bling']
