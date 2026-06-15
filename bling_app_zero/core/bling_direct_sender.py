from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd
import streamlit as st

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_token_store import load_token
from bling_app_zero.core.operation_contract import OP_ATUALIZACAO_PRECO, OP_CADASTRO, OP_ESTOQUE, normalize_operation, operation_label
from bling_app_zero.core.operation_safety_guard import require_rows_before_api

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_direct_sender.py'
DEFAULT_API_BASE_URL = 'https://www.bling.com.br/Api/v3'
DIRECT_SAFE_OPERATIONS = {OP_CADASTRO, OP_ESTOQUE, OP_ATUALIZACAO_PRECO}


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


def _token() -> tuple[dict[str, Any] | None, str]:
    token, meta = load_token()
    if not isinstance(token, dict) or not token.get('access_token'):
        return None, str(meta.get('store_mode') or '')
    return token, str(meta.get('store_mode') or '')


def is_direct_send_available() -> bool:
    token, _mode = _token()
    return isinstance(token, dict) and bool(token.get('access_token'))


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
        {
            'stage': 'Envio bloqueado antes da API',
            'operation': normalized,
            'processed': 0,
            'total': 0,
            'sent': 0,
            'failed': 0,
            'skipped': 0,
            'progress': 1.0,
            'blocked_before_api': True,
            'reason': decision.reason or 'sem_linhas',
        },
    )
    add_audit_event(
        'bling_direct_sender_blocked_empty_before_api',
        area='BLING_ENVIO',
        status='BLOQUEADO',
        details={
            'operation': normalized,
            'message': message,
            'reason': decision.reason or 'sem_linhas',
            'decision_details': decision.details or {},
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return DirectSendResult(0, 0, 0, 0, (message,), tuple())


def preview_payloads(df: pd.DataFrame, operation: str, *, limit: int = 5) -> list[dict[str, Any]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return []
    normalized = normalize_operation(operation)
    if normalized in DIRECT_SAFE_OPERATIONS:
        try:
            from bling_app_zero.core.bling_direct_sender_safe import preview_payloads as _safe_preview_payloads

            return _safe_preview_payloads(df, normalized, limit=limit)
        except Exception as exc:
            add_audit_event(
                'bling_direct_sender_preview_safe_delegate_failed',
                area='BLING_ENVIO',
                status='AVISO',
                details={'operation': normalized, 'error': str(exc)[:220], 'responsible_file': RESPONSIBLE_FILE},
            )
    previews: list[dict[str, Any]] = []
    for _index, row in df.fillna('').head(limit).iterrows():
        payload = {str(column): row.get(column, '') for column in df.columns if str(row.get(column, '')).strip()}
        previews.append({'payload': payload, 'status': 'OK' if payload else 'IGNORADO', 'motivo': '' if payload else 'Linha vazia.'})
    return previews


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

    if normalized in DIRECT_SAFE_OPERATIONS:
        try:
            from bling_app_zero.core.bling_direct_sender_safe import send_dataframe_to_bling as _safe_send_dataframe_to_bling

            add_audit_event(
                'bling_direct_sender_delegated_to_safe_sender',
                area='BLING_ENVIO',
                status='OK',
                details={
                    'operation': normalized,
                    'rows': len(df),
                    'reason': 'Sender bruto convertido em camada segura; cadastro, estoque e preço são delegados ao sender seguro com guard preventivo.',
                    'responsible_file': RESPONSIBLE_FILE,
                },
            )
            return _safe_send_dataframe_to_bling(df, normalized, limit=limit, progress_callback=progress_callback)
        except Exception as exc:
            add_audit_event(
                'bling_direct_sender_safe_delegate_failed',
                area='BLING_ENVIO',
                status='ERRO',
                details={'operation': normalized, 'rows': len(df), 'error': str(exc)[:300], 'responsible_file': RESPONSIBLE_FILE},
            )
            return DirectSendResult(len(df), 0, len(df), 0, (f'Falha ao delegar envio seguro ao Bling: {exc}',), tuple())

    message = f'Operação sem envio direto configurado no sender bruto: {operation_label(normalized)}.'
    add_audit_event(
        'bling_direct_sender_unsupported_operation_blocked',
        area='BLING_ENVIO',
        status='BLOQUEADO',
        details={'operation': normalized, 'rows': len(df), 'message': message, 'responsible_file': RESPONSIBLE_FILE},
    )
    return DirectSendResult(len(df), 0, 0, len(df), (message,), tuple())


__all__ = ['DirectSendResult', 'api_base_url', 'is_direct_send_available', 'preview_payloads', 'send_dataframe_to_bling']
