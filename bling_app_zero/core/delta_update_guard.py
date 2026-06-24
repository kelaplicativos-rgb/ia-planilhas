from __future__ import annotations

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.operation_contract import OP_ATUALIZACAO_PRECO, OP_ESTOQUE, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/core/delta_update_guard.py'


def _safe_original(df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    return df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame(), []


def filter_changed_rows_before_api(df: pd.DataFrame, operation: str, *, limit: int | None = None) -> tuple[pd.DataFrame, list[dict]]:
    """Contrato central: linhas iguais devem ser puladas antes da API quando houver comparador instalado.

    Se o comparador específico ainda não estiver disponível ou não conseguir ler o dado atual no Bling,
    o guard não quebra o envio: mantém a linha para o sender normal decidir. Produto existente já usa
    delta real no sender verificado; preço e estoque passam por este contrato quando seus comparadores
    estiverem disponíveis.
    """
    op = normalize_operation(operation)
    rows = (df.fillna('').head(limit) if limit and isinstance(df, pd.DataFrame) else df.fillna('')) if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if rows.empty:
        return rows.copy(), []
    try:
        if op == OP_ATUALIZACAO_PRECO:
            from bling_app_zero.core.bling_price_sender_guarded import filter_price_rows_changed_before_api
            return filter_price_rows_changed_before_api(rows)
        if op == OP_ESTOQUE:
            from bling_app_zero.core.bling_direct_sender_safe import filter_stock_rows_changed_before_api
            return filter_stock_rows_changed_before_api(rows)
    except Exception as exc:
        add_audit_event(
            'delta_update_guard_comparator_unavailable_keep_rows',
            area='BLING_ENVIO',
            status='AVISO',
            details={'operation': op, 'rows': len(rows), 'error': str(exc)[:240], 'fallback': 'mantem_linhas_para_sender_normal', 'responsible_file': RESPONSIBLE_FILE},
        )
    return _safe_original(rows)


__all__ = ['filter_changed_rows_before_api']
