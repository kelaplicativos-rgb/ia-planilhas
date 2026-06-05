from __future__ import annotations

from typing import Any, Callable

import pandas as pd
import requests

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_direct_sender import DirectSendResult
from bling_app_zero.core.bling_direct_sender_smart import (
    RESPONSIBLE_FILE as BASE_RESPONSIBLE_FILE,
    SEND_TIMEOUT,
    _cadastro_schema_error,
    _emit_progress,
    _headers,
    _payload_variants,
    _resolve_product_id,
    _secret,
    _url,
    is_direct_send_available,
    preview_payloads,
)
from bling_app_zero.core.bling_smart_product_diff import update_existing_product_if_changed
from bling_app_zero.core.bling_token_store import load_token
from bling_app_zero.core.bling_direct_sender_safe import send_dataframe_to_bling as _safe_send_dataframe_to_bling
from bling_app_zero.core.operation_contract import OP_CADASTRO, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_direct_sender_smart_diff.py'


def _update_existing_product_diff(
    token: dict[str, Any],
    product_id: str,
    variants: list[tuple[str, dict[str, Any], dict[str, Any]]],
) -> tuple[str, list[dict[str, Any]]]:
    return update_existing_product_if_changed(
        token=token,
        product_id=product_id,
        variants=variants,
        url_builder=_url,
        headers_builder=_headers,
        timeout=SEND_TIMEOUT,
        responsible_file=RESPONSIBLE_FILE,
    )


def _send_cadastro_smart_diff(
    df: pd.DataFrame,
    *,
    limit: int | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> DirectSendResult:
    schema_error = _cadastro_schema_error(df)
    if schema_error:
        total = len(df) if isinstance(df, pd.DataFrame) else 0
        return DirectSendResult(total, 0, 0, total, (schema_error,), tuple())

    token, _meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return DirectSendResult(0, 0, 0, len(df) if isinstance(df, pd.DataFrame) else 0, ('Bling não conectado. Conecte o app antes de enviar direto.',))

    rows = df.fillna('').head(limit) if limit else df.fillna('')
    from bling_app_zero.core.bling_direct_sender_smart import _column_map

    mapping = _column_map(rows.columns)
    total = len(rows)
    sent = failed = skipped = 0
    errors: list[str] = []
    create_path = _secret('product_create_path', '/produtos') or '/produtos'

    _emit_progress(progress_callback, {'stage': 'Iniciando cadastro inteligente com comparação', 'processed': 0, 'total': total, 'sent': 0, 'failed': 0, 'skipped': 0, 'progress': 0.0})

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
            update_status, update_attempts = _update_existing_product_diff(token, existing_id, variants)
            if update_status == 'updated':
                sent += 1
                add_audit_event('bling_smart_diff_product_updated', area='BLING_ENVIO', status='OK', details={'line': line, 'product_id': existing_id, 'attempts': update_attempts[-3:], 'responsible_file': RESPONSIBLE_FILE, 'base_file': BASE_RESPONSIBLE_FILE})
                _emit_progress(progress_callback, {'stage': 'Produto alterado atualizado', 'processed': position, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': position / max(total, 1)})
                continue
            if update_status == 'unchanged':
                skipped += 1
                add_audit_event('bling_smart_diff_product_skipped_unchanged', area='BLING_ENVIO', status='PULADO', details={'line': line, 'product_id': existing_id, 'responsible_file': RESPONSIBLE_FILE})
                _emit_progress(progress_callback, {'stage': 'Sem alteração: pulado', 'processed': position, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': position / max(total, 1)})
                continue

        ok = False
        attempts: list[dict[str, Any]] = []
        last_response: requests.Response | None = None
        for strategy, payload, meta in variants:
            try:
                response = requests.post(_url(create_path), headers=_headers(token), json=payload, timeout=SEND_TIMEOUT)
                last_response = response
                response_text = str(response.text or '')
                attempts.append({'mode': 'create', 'strategy': strategy, 'status': int(response.status_code), 'confidence': meta.get('confidence'), 'payload_keys': sorted(payload.keys()), 'response_preview': response_text[:500]})
                if response.status_code < 400:
                    ok = True
                    add_audit_event('bling_smart_diff_product_created', area='BLING_ENVIO', status='OK', details={'line': line, 'strategy': strategy, 'responsible_file': RESPONSIBLE_FILE})
                    break
                if response.status_code == 400 and ('código' in response_text.lower() or 'codigo' in response_text.lower()):
                    resolved_after_error = _resolve_product_id(token, candidates)
                    if resolved_after_error:
                        update_status, update_attempts = _update_existing_product_diff(token, resolved_after_error, variants)
                        attempts.extend(update_attempts[-4:])
                        if update_status == 'updated':
                            ok = True
                            break
                        if update_status == 'unchanged':
                            skipped += 1
                            ok = True
                            break
                if response.status_code in {401, 403}:
                    break
            except Exception as exc:
                attempts.append({'mode': 'create', 'strategy': strategy, 'status': 'EXCEPTION', 'error': str(exc)[:240]})

        if ok and not any(item.get('mode') == 'skip_unchanged' for item in attempts):
            sent += 1
        elif not ok:
            failed += 1
            status = getattr(last_response, 'status_code', 'sem resposta')
            preview = str(getattr(last_response, 'text', '') or '')[:700]
            if len(errors) < 8:
                errors.append(f'Linha {line}: Bling recusou cadastro/upsert inteligente ({status}) após {len(variants)} tentativa(s). {preview}')
            add_audit_event('bling_smart_diff_product_failed', area='BLING_ENVIO', status='AVISO', details={'line': line, 'status': status, 'attempts': attempts[-8:], 'responsible_file': RESPONSIBLE_FILE})

        _emit_progress(progress_callback, {'stage': 'Cadastrando no Bling com comparação', 'processed': position, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': position / max(total, 1)})

    _emit_progress(progress_callback, {'stage': 'Cadastro inteligente com comparação concluído', 'processed': total, 'total': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'progress': 1.0})
    add_audit_event('bling_smart_diff_finished', area='BLING_ENVIO', status='OK' if failed == 0 else 'PARCIAL', details={'attempted': total, 'sent': sent, 'failed': failed, 'skipped': skipped, 'mode': 'diff_update_only_changed_create_new_skip_unchanged', 'responsible_file': RESPONSIBLE_FILE})
    return DirectSendResult(total, sent, failed, skipped, tuple(errors), tuple())


def send_dataframe_to_bling(
    df: pd.DataFrame,
    operation: str,
    *,
    limit: int | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> DirectSendResult:
    if normalize_operation(operation) == OP_CADASTRO:
        return _send_cadastro_smart_diff(df, limit=limit, progress_callback=progress_callback)
    return _safe_send_dataframe_to_bling(df, operation, limit=limit, progress_callback=progress_callback)


__all__ = ['DirectSendResult', 'is_direct_send_available', 'preview_payloads', 'send_dataframe_to_bling']
