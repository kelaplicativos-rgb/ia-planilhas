from __future__ import annotations

"""Blindagem de colunas equivalentes de estoque.

Objetivo do sistema de atualização de estoque:
- o valor disponível capturado do estoque é soberano;
- colunas de destino do Bling como Balanço/Estoque/Quantidade não podem ficar
  divergentes na mesma linha;
- quando houver colunas de origem real como Estoque ou Quantidade, elas vencem
  sobre Balanço, porque Balanço é o destino do Bling.
"""

import re
import unicodedata
from typing import Iterable

import pandas as pd


def normalize_key(value: object) -> str:
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def is_stock_column(column: object) -> bool:
    key = normalize_key(column)
    return any(term in key for term in ("balanco", "saldo", "estoque", "quantidade", "qtd"))


def is_balance_column(column: object) -> bool:
    key = normalize_key(column)
    return "balanco" in key or key in {"saldo"}


def is_real_quantity_column(column: object) -> bool:
    key = normalize_key(column)
    return any(term in key for term in ("estoque", "quantidade", "qtd")) and "origem" not in key and "fonte" not in key and "confianca" not in key


def is_stock_origin_column(column: object) -> bool:
    key = normalize_key(column)
    return any(term in key for term in ("origem do estoque", "origem estoque", "fonte estoque", "confianca estoque", "confianca do estoque"))


def _to_number(value: object) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    key = normalize_key(text)
    if key in {"nan", "none", "null", "nat"}:
        return None
    if any(term in key for term in ("sem estoque", "indisponivel", "esgotado", "fora de estoque")):
        return 0.0
    match = re.search(r"-?\d+(?:[\.,]\d+)?", text)
    if not match:
        return None
    try:
        number = float(match.group(0).replace(",", "."))
    except Exception:
        return None
    if number < 0:
        return None
    return number


def _format_number(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return str(value).rstrip("0").rstrip(".")


def _has_real_origin(row: pd.Series) -> bool:
    for col in row.index:
        if not is_stock_origin_column(col):
            continue
        value = normalize_key(row.get(col, ""))
        if value and value not in {"fallback", "fallback disponivel sem quantidade", "baixa", "nao encontrado"}:
            return True
    return False


def _canonical_stock_value(row: pd.Series, stock_cols: list[str]) -> str:
    real_quantity_cols = [col for col in stock_cols if is_real_quantity_column(col)]
    balance_cols = [col for col in stock_cols if is_balance_column(col)]

    # 1) Se há origem real declarada, prioriza Estoque/Quantidade mesmo quando
    # o valor é 0. Isso corrige Balanço=1 vs Estoque=0/Quantidade=0.
    if _has_real_origin(row):
        for col in real_quantity_cols:
            number = _to_number(row.get(col, ""))
            if number is not None:
                return _format_number(number)

    # 2) Mesmo sem coluna de origem, Estoque/Quantidade são colunas de captura.
    # Se elas existem, elas vencem o Balanço de destino.
    for col in real_quantity_cols:
        number = _to_number(row.get(col, ""))
        if number is not None:
            return _format_number(number)

    # 3) Sem valor capturado, usa Balanço/Saldo se for o único valor disponível.
    for col in balance_cols:
        number = _to_number(row.get(col, ""))
        if number is not None:
            return _format_number(number)

    # 4) Último recurso: qualquer coluna equivalente.
    for col in stock_cols:
        number = _to_number(row.get(col, ""))
        if number is not None:
            return _format_number(number)
    return ""


def synchronize_stock_columns(df: pd.DataFrame, requested_columns: Iterable[str] | None = None) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()

    out = df.copy().fillna("")
    scope = [str(col or "").strip() for col in (requested_columns or out.columns) if str(col or "").strip()]
    stock_cols = [col for col in scope if col in out.columns and is_stock_column(col)]
    if len(stock_cols) <= 1:
        return out.fillna("")

    for idx, row in out.iterrows():
        canonical = _canonical_stock_value(row, stock_cols)
        if canonical == "":
            continue
        for col in stock_cols:
            out.at[idx, col] = canonical
    return out.fillna("")


def keep_requested_and_sync_stock(df: pd.DataFrame, requested_columns: Iterable[str]) -> pd.DataFrame:
    requested = [str(col or "").strip() for col in requested_columns if str(col or "").strip()]
    if not requested:
        return pd.DataFrame()

    base = df.copy().fillna("") if isinstance(df, pd.DataFrame) else pd.DataFrame()
    output = pd.DataFrame(index=base.index)
    existing_by_key = {normalize_key(col): col for col in base.columns}

    for requested_col in requested:
        existing = existing_by_key.get(normalize_key(requested_col))
        output[requested_col] = base[existing].astype(str).fillna("") if existing is not None else ""

    return synchronize_stock_columns(output, requested).fillna("")


__all__ = [
    "is_balance_column",
    "is_real_quantity_column",
    "is_stock_column",
    "is_stock_origin_column",
    "keep_requested_and_sync_stock",
    "normalize_key",
    "synchronize_stock_columns",
]
