from __future__ import annotations

import pandas as pd

from bling_app_zero.core.column_contract import RequestedField
from bling_app_zero.engines.fast_site_scraper.contract_rules import value_for_kind
from bling_app_zero.engines.fast_site_scraper.models import FastProductData


def to_contract_row(product: FastProductData, contract: list[RequestedField]) -> dict[str, str]:
    row: dict[str, str] = {}
    for field in contract:
        row[field.original] = value_for_kind(product, field.kind)
    return row


def _drop_blank_rows(df: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    work = df.copy().fillna('')
    text = work.astype(str).apply(lambda column: column.str.strip())
    mask = text.ne('').any(axis=1)
    return work.loc[mask].reset_index(drop=True)


def ensure_columns(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    for column in columns:
        if column not in out.columns:
            out[column] = ''
    out = out.loc[:, columns].fillna('')
    return _drop_blank_rows(out).fillna('')


__all__ = ['ensure_columns', 'to_contract_row']
