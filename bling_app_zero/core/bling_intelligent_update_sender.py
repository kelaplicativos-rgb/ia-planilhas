from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_api_base_patch import patch_bling_api_base_urls
from bling_app_zero.core.bling_direct_sender import DirectSendResult
from bling_app_zero.core.bling_direct_sender_smart_diff import send_dataframe_to_bling as _smart_diff_send_dataframe_to_bling
from bling_app_zero.core.bling_pre_send_defaults import apply_dataframe_send_defaults, apply_product_send_defaults
from bling_app_zero.core.bling_product_update_intelligence import ACTION_PENDING, analyze_product_update_need, analyze_stock_update_need
from bling_app_zero.core.operation_contract import OP_ESTOQUE, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_intelligent_update_sender.py'


def _emit(progress_callback: Callable[[dict[str, Any]], None] | None, payload: dict[str, Any]) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(payload)
    except Exception:
        pass


def _safe_int_attr(obj: object, *names: str, default: int = 0) -> int:
    for name in names:
        try:
            value = getattr(obj, name)
        except Exception:
            continue
        try:
            return int(value or 0)
        except Exception:
            continue
    return int(default or 0)


def _safe_tuple_attr(obj: object, name: str) -> tuple[Any, ...]:
    try:
        value = getattr(obj, name)
    except Exception:
        return tuple()

    if value is None:
        return tuple()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return (value,)


def _pending_reason_text(item: dict[str, Any]) -> str:
    for key in ('reason', 'motivo', 'message', 'mensagem', 'title', 'titulo'):
        value = str(item.get(key) or '').strip()
        if value:
            return value
    reasons = item.get('reasons')
    if isinstance(reasons, (list, tuple)):
        joined = '; '.join(str(part or '').strip() for part in reasons if str(part or '').strip())
        if joined:
            return joined
    return 'pendência inteligente antes da API'


def _pending_errors_by_line(pending: list[dict[str, Any]], *, limit: int = 120) -> list[str]:
    errors: list[str] = []
    for item in pending[:limit]:
        try:
            line = int(item.get('line') or 0)
        except Exception:
            line = 0
        reason = _pending_reason_text(item)
        if line > 0:
            errors.append(f'linha {line}: pendência inteligente antes da API. {reason}')
        else:
            errors.append(f'pendência inteligente antes da API. {reason}')
    extra = len(pending) - len(errors)
    if extra > 0:
        errors.append(f'{extra} linha(s) adicionais ficaram como pendência inteligente antes da API sem detalhamento exibido.')
    return errors


def _decision_for_operation(row: Any, operation: str):
    op = normalize_operation(operation)
    prepared_row = apply_product_send_defaults(row)
    if op == OP_ESTOQUE:
        return analyze_stock_update_need(prepared_row)
    return analyze_product_update_need(prepared_row, None)


def split_intelligent_update_rows(df: pd.DataFrame, operation: str = '') -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(), []

    op = normalize_operation(operation)
    prepared_df = apply_dataframe_send_defaults(df)
    allowed_indices: list[Any] = []
    pending: list[dict[str, Any]] = []
    for position, (index, row) in enumerate(prepared_df.fillna('').iterrows(), start=1):
        line = int(index) + 1 if isinstance(index, int) else position
        decision = _decision_for_operation(row, op)
        payload = decision.to_dict()
        payload['line'] = line
        payload['operation'] = op
        payload['pre_send_defaults_applied'] = True
        if decision.action == ACTION_PENDING or decision.should_hold:
            pending.append(payload)
            continue
        allowed_indices.append(index)
    if not allowed_indices:
        return pd.DataFrame(columns=list(prepared_df.columns)), pending
    return prepared_df.loc[allowed_indices].copy().fillna(''), pending


def send_dataframe_to_bling_intelligent(
    df: pd.DataFrame,
    operation: str,
    *,
    limit: int | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> DirectSendResult:
    """Envio com pré-decisão inteligente antes do sender atual.

    BLINGFIX: antes de qualquer chamada API, corrige em runtime os módulos que
    ainda carregaram o default legado www.bling.com.br/Api/v3 e aplica defaults
    mínimos antes da pré-decisão para evitar bloqueio indevido por nome ausente
    quando há descrição/código confiável.
    """
    patch_bling_api_base_urls()

    if not isinstance(df, pd.DataFrame) or df.empty:
        return DirectSendResult(0, 0, 0, 0, tuple(), tuple())

    op = normalize_operation(operation)
    allowed_df, pending = split_intelligent_update_rows(df, op)
    skipped_before_api = len(pending)
    for item in pending[:50]:
        add_audit_event(
            'bling_intelligent_update_pending_before_api',
            area='BLING_ENVIO',
            status='PENDENCIA',
            details={'operation': op, 'decision': item, 'responsible_file': RESPONSIBLE_FILE},
        )

    _emit(
        progress_callback,
        {
            'stage': 'Pré-decisão inteligente de atualização',
            'operation': op,
            'processed': 0,
            'total': len(df),
            'sent': 0,
            'failed': 0,
            'skipped': skipped_before_api,
            'pending_before_api': skipped_before_api,
            'allowed_rows': len(allowed_df),
            'progress': 0.02,
            'stock_quality_mode': op == OP_ESTOQUE,
            'pre_send_defaults_applied': True,
        },
    )

    pending_errors = _pending_errors_by_line(pending)

    if allowed_df.empty:
        message = 'Todas as linhas viraram pendência inteligente antes da API; nada foi enviado ao Bling.'
        add_audit_event(
            'bling_intelligent_update_all_pending_before_api',
            area='BLING_ENVIO',
            status='BLOQUEADO',
            details={'operation': op, 'total': len(df), 'pending': skipped_before_api, 'stock_quality_mode': op == OP_ESTOQUE, 'pre_send_defaults_applied': True, 'responsible_file': RESPONSIBLE_FILE},
        )
        return DirectSendResult(len(df), 0, 0, skipped_before_api, tuple([message] + pending_errors), tuple())

    result = _smart_diff_send_dataframe_to_bling(
        allowed_df,
        op,
        limit=limit,
        progress_callback=progress_callback,
    )

    attempted_after_api = _safe_int_attr(result, 'attempted', 'total', default=len(allowed_df))
    sent = _safe_int_attr(result, 'sent', default=0)
    failed = _safe_int_attr(result, 'failed', default=0)
    skipped_after_api = _safe_int_attr(result, 'skipped', default=0)

    attempted_total = attempted_after_api + skipped_before_api
    skipped_total = skipped_after_api + skipped_before_api

    errors = list(_safe_tuple_attr(result, 'errors'))
    if skipped_before_api:
        errors.extend(pending_errors)
        errors.append(f'{skipped_before_api} linha(s) ficaram como pendência inteligente antes da API.')

    not_found_indices = _safe_tuple_attr(result, 'not_found_indices')

    add_audit_event(
        'bling_intelligent_update_sender_finished',
        area='BLING_ENVIO',
        status='OK' if failed == 0 else 'PARCIAL',
        details={
            'operation': op,
            'total_input': len(df),
            'attempted_after_api': attempted_after_api,
            'attempted_total': attempted_total,
            'allowed_rows': len(allowed_df),
            'pending_before_api': skipped_before_api,
            'sent': sent,
            'failed': failed,
            'skipped_after_api': skipped_after_api,
            'skipped_total': skipped_total,
            'stock_quality_mode': op == OP_ESTOQUE,
            'api_base_patch_enabled': True,
            'pre_send_defaults_applied': True,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return DirectSendResult(attempted_total, sent, failed, skipped_total, tuple(errors), not_found_indices)


__all__ = ['send_dataframe_to_bling_intelligent', 'split_intelligent_update_rows']
