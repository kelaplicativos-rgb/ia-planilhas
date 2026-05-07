from __future__ import annotations

"""Guarda final das colunas equivalentes de estoque.

Este módulo NÃO busca estoque e NÃO cria fallback de disponibilidade.
Ele só sincroniza valores já capturados pelos módulos novos:
- stock_value_engine.py
- stock_feed_engine.py
- estoque_fast_crawler.py

Regra soberana:
Estoque/Quantidade/Qtd capturados vencem Balanço/Saldo de destino.
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
    return "balanco" in key or key == "saldo"


def is_real_quantity_column(column: object) -> bool:
    key = normalize_key(column)
    if any(term in key for term in ("origem", "fonte", "confianca")):
        return False
    return any(term in key for term in ("estoque", "quantidade", "qtd"))


def is_stock_origin_column(column: object) -> bool:
    key = normalize_key(column)
    return any(term in key for term in ("origem estoque", "origem do estoque", "fonte estoque", "confianca estoque", "confianca do estoque"))


def normalize_stock_value(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    key = normalize_key(text)
    if key in {"nan", "none", "null", "nat"}:
        return ""
    if any(term in key for term in ("sem estoque", "indisponivel", "esgotado", "fora de estoque")):
        return "0"
    match = re.search(r"-?\d+(?:[\.,]\d+)?", text)
    if not match:
        return ""
    try:
        number = float(match.group(0).replace(",", "."))
    except Exception:
        return ""
    if number < 0:
        return ""
    if number.is_integer():
        return str(int(number))
    return str(number).rstrip("0").rstrip(".")


def _has_real_origin(row: pd.Series) -> bool:
    for col in row.index:
        if not is_stock_origin_column(col):
            continue
        value = normalize_key(row.get(col, ""))
        if not value:
            continue
        if value in {"fallback", "fallback disponivel sem quantidade", "baixa", "nao encontrado", "nenhuma"}:
            continue
        return True
    return False


def _canonical_stock_value(row: pd.Series, stock_cols: list[str]) -> str:
    real_cols = [col for col in stock_cols if is_real_quantity_column(col)]
    balance_cols = [col for col in stock_cols if is_balance_column(col)]

    if _has_real_origin(row):
        for col in real_cols:
            value = normalize_stock_value(row.get(col, ""))
            if value != "":
                return value

    for col in real_cols:
        value = normalize_stock_value(row.get(col, ""))
        if value != "":
            return value

    for col in balance_cols:
        value = normalize_stock_value(row.get(col, ""))
        if value != "":
            return value

    for col in stock_cols:
        value = normalize_stock_value(row.get(col, ""))
        if value != "":
            return value
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
    "normalize_stock_value",
    "synchronize_stock_columns",
]
