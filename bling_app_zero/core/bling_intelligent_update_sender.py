from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.bling_direct_sender import DirectSendResult
from bling_app_zero.core.bling_direct_sender_smart_diff import send_dataframe_to_bling as _smart_diff_send_dataframe_to_bling
from bling_app_zero.core.bling_product_update_intelligence import ACTION_PENDING, analyze_product_update_need

RESPONSIBLE_FILE = 'bling_app_zero/core/bling_intelligent_update_sender.py'


def _emit(progress_callback: Callable[[dict[str, Any]], None] | None, payload: dict[str, Any]) -> None:
    if not progress_callback:
        return
    try:
        progress_callback(payload)
    except Exception:
        pass


def split_intelligent_update_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(), []

    allowed_indices: list[Any] = []
    pending: list[dict[str, Any]] = []
    for position, (index, row) in enumerate(df.fillna('').iterrows(), start=1):
        line = int(index) + 1 if isinstance(index, int) else position
        decision = analyze_product_update_need(row, None)
        payload = decision.to_dict()
        payload['line'] = line
        if decision.action == ACTION_PENDING or decision.should_hold:
            pending.append(payload)
            continue
        allowed_indices.append(index)
    if not allowed_indices:
        return pd.DataFrame(columns=list(df.columns)), pending
    return df.loc[allowed_indices].copy().fillna(''), pending


def send_dataframe_to_bling_intelligent(
    df: pd.DataFrame,
    operation: str,
    *,
    limit: int | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> DirectSendResult:
    """Envio com pré-decisão de qualidade antes do sender atual.

    Este wrapper não substitui o comparador existente; ele apenas evita gastar API
    com linhas que já sabemos que virariam pendência por falta de identidade/nome.
    O sender smart_diff continua fazendo a comparação profunda contra o Bling e
    atualiza somente produtos com mudança real.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return DirectSendResult(0, 0, 0, 0, tuple(), tuple())

    allowed_df, pending = split_intelligent_update_rows(df)
    skipped_before_api = len(pending)
    for item in pending[:50]:
        add_audit_event(
            'bling_intelligent_update_pending_before_api',
            area='BLING_ENVIO',
            status='PENDENCIA',
            details={'decision': item, 'responsible_file': RESPONSIBLE_FILE},
        )

    _emit(
        progress_callback,
        {
            'stage': 'Pré-decisão inteligente de atualização',
            'processed': 0,
            'total': len(df),
            'sent': 0,
            'failed': 0,
            'skipped': skipped_before_api,
            'pending_before_api': skipped_before_api,
            'allowed_rows': len(allowed_df),
            'progress': 0.02,
        },
    )

    if allowed_df.empty:
        message = 'Todas as linhas viraram pendência inteligente antes da API; nada foi enviado ao Bling.'
        add_audit_event(
            'bling_intelligent_update_all_pending_before_api',
            area='BLING_ENVIO',
            status='BLOQUEADO',
            details={'total': len(df), 'pending': skipped_before_api, 'responsible_file': RESPONSIBLE_FILE},
        )
        return DirectSendResult(len(df), 0, 0, skipped_before_api, (message,), tuple())

    result = _smart_diff_send_dataframe_to_bling(
        allowed_df,
        operation,
        limit=limit,
        progress_callback=progress_callback,
    )
    total = int(result.total) + skipped_before_api
    skipped = int(result.skipped) + skipped_before_api
    errors = tuple(list(result.errors or ()) + [f'{skipped_before_api} linha(s) ficaram como pendência inteligente antes da API.'] if skipped_before_api else list(result.errors or ()))
    add_audit_event(
        'bling_intelligent_update_sender_finished',
        area='BLING_ENVIO',
        status='OK' if int(result.failed) == 0 else 'PARCIAL',
        details={
            'total_input': len(df),
            'allowed_rows': len(allowed_df),
            'pending_before_api': skipped_before_api,
            'sent': int(result.sent),
            'failed': int(result.failed),
            'skipped_total': skipped,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return DirectSendResult(total, int(result.sent), int(result.failed), skipped, errors, result.not_found_indices)


__all__ = ['send_dataframe_to_bling_intelligent', 'split_intelligent_update_rows']
