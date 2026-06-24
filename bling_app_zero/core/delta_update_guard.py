from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.operation_contract import OP_ATUALIZACAO_PRECO, OP_ESTOQUE, normalize_operation

RESPONSIBLE_FILE = 'bling_app_zero/core/delta_update_guard.py'
PRICE_TOLERANCE = 0.005
STOCK_TOLERANCE = 0.0001

PRICE_DESIRED_ALIASES = ('preco', 'preço', 'preco unitario', 'preço unitário', 'valor', 'valor venda', 'preco de venda', 'preço de venda')
PRICE_CURRENT_ALIASES = ('preco atual', 'preço atual', 'preco atual bling', 'preço atual bling', 'preco no bling', 'preço no bling', 'bling preco atual', 'bling preço atual')
STOCK_DESIRED_ALIASES = ('estoque', 'saldo', 'quantidade', 'qtd', 'qtde')
STOCK_CURRENT_ALIASES = ('estoque atual', 'saldo atual', 'quantidade atual', 'saldo atual bling', 'estoque atual bling', 'bling saldo atual', 'bling estoque atual')


def _norm(value: object) -> str:
    text = str(value or '').strip().lower()
    for old, new in {'ã': 'a', 'á': 'a', 'à': 'a', 'â': 'a', 'é': 'e', 'ê': 'e', 'í': 'i', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ú': 'u', 'ç': 'c'}.items():
        text = text.replace(old, new)
    return ' '.join(''.join(ch if ch.isalnum() else ' ' for ch in text).split())


def _number(value: Any) -> float | None:
    text = str(value or '').strip().replace('R$', '').replace('\xa0', '').replace(' ', '')
    if not text:
        return None
    text = text.replace('.', '').replace(',', '.') if ',' in text and '.' in text else text.replace(',', '.')
    text = ''.join(ch for ch in text if ch in '-0123456789.')
    try:
        return float(text) if text not in {'', '-', '.', '-.'} else None
    except Exception:
        return None


def _find_column(columns: list[object], aliases: tuple[str, ...]) -> str:
    normalized = {_norm(column): str(column) for column in columns}
    for alias in aliases:
        found = normalized.get(_norm(alias))
        if found:
            return found
    for column in columns:
        token = _norm(column)
        if any(_norm(alias) in token for alias in aliases):
            return str(column)
    return ''


def _local_delta_filter(df: pd.DataFrame, operation: str) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame(), []
    columns = list(df.columns)
    op = normalize_operation(operation)
    if op == OP_ATUALIZACAO_PRECO:
        desired_col = _find_column(columns, PRICE_DESIRED_ALIASES)
        current_col = _find_column(columns, PRICE_CURRENT_ALIASES)
        tolerance = PRICE_TOLERANCE
    elif op == OP_ESTOQUE:
        desired_col = _find_column(columns, STOCK_DESIRED_ALIASES)
        current_col = _find_column(columns, STOCK_CURRENT_ALIASES)
        tolerance = STOCK_TOLERANCE
    else:
        return df.copy().fillna(''), []
    if not desired_col or not current_col or desired_col == current_col:
        return df.copy().fillna(''), []

    keep: list[Any] = []
    skipped: list[dict[str, Any]] = []
    for position, (index, row) in enumerate(df.fillna('').iterrows(), start=1):
        desired = _number(row.get(desired_col))
        current = _number(row.get(current_col))
        if desired is None or current is None:
            keep.append(index)
            continue
        if abs(float(desired) - float(current)) <= tolerance:
            skipped.append({'line': int(index) + 1 if isinstance(index, int) else position, 'operation': op, 'current_column': current_col, 'desired_column': desired_col, 'current': current, 'desired': desired, 'reason': 'valor_atual_igual_ao_desejado'})
        else:
            keep.append(index)
    if skipped:
        add_audit_event('delta_update_guard_local_skipped_unchanged_rows_before_api', area='BLING_ENVIO', status='OK', details={'operation': op, 'input_rows': len(df), 'changed_rows': len(keep), 'skipped_unchanged': len(skipped), 'current_column': current_col, 'desired_column': desired_col, 'sample': skipped[:12], 'responsible_file': RESPONSIBLE_FILE})
    return (df.loc[keep].copy().fillna('') if keep else pd.DataFrame(columns=list(df.columns))), skipped


def filter_changed_rows_before_api(df: pd.DataFrame, operation: str, *, limit: int | None = None) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    op = normalize_operation(operation)
    rows = (df.fillna('').head(limit) if limit and isinstance(df, pd.DataFrame) else df.fillna('')) if isinstance(df, pd.DataFrame) else pd.DataFrame()
    if rows.empty:
        return rows.copy(), []
    return _local_delta_filter(rows, op)


__all__ = ['filter_changed_rows_before_api']
