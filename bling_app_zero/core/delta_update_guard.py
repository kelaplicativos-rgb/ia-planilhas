from __future__ import annotations

import pandas as pd

from bling_app_zero.core.operation_contract import OP_ATUALIZACAO_PRECO, OP_ESTOQUE, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/core/delta_update_guard.py'


def filter_changed_rows_before_api(df: pd.DataFrame, operation: str, *, limit: int | None = None) -> tuple[pd.DataFrame, list[dict]]:
    """Contrato central: linhas iguais devem ser puladas antes da API quando houver comparador instalado.

    O comparador real fica nos senders específicos para evitar duplicar credenciais e chamadas HTTP.
    Se não houver comparador para a operação, retorna a tabela original.
    """
    op = normalize_operation(operation)
    rows = (df.fillna('').head(limit) if limit and isinstance(df, pd.DataFrame) else df.fillna('')) if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if op == OP_ATUALIZACAO_PRECO:
        from bling_app_zero.core.bling_price_sender_guarded import filter_price_rows_changed_before_api
        return filter_price_rows_changed_before_api(rows)
    if op == OP_ESTOQUE:
        from bling_app_zero.core.bling_direct_sender_safe import filter_stock_rows_changed_before_api
        return filter_stock_rows_changed_before_api(rows)
    return rows.copy().fillna(''), []


__all__ = ['filter_changed_rows_before_api']
