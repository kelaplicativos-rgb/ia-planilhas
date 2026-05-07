from __future__ import annotations

from typing import Any

import pandas as pd


def to_number(value: Any) -> float:
    text = str(value or '').strip()
    if not text:
        return 0.0
    text = text.replace('R$', '').replace(' ', '')
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    elif ',' in text:
        text = text.replace(',', '.')
    try:
        return float(text)
    except Exception:
        return 0.0


def calculate_price(cost: float, margin: float = 0.0, tax: float = 0.0, fee: float = 0.0, fixed: float = 0.0) -> float:
    base = float(cost or 0.0) + float(fixed or 0.0)
    multiplier = 1 + ((float(margin or 0.0) + float(tax or 0.0) + float(fee or 0.0)) / 100.0)
    return round(base * multiplier, 2)


def apply_pricing(df: pd.DataFrame, cost_column: str, output_column: str, margin: float = 0.0, tax: float = 0.0, fee: float = 0.0, fixed: float = 0.0) -> pd.DataFrame:
    if df is None or not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    if df.empty or cost_column not in df.columns:
        return df.copy()
    out = df.copy().fillna('')
    out[output_column] = out[cost_column].apply(lambda v: calculate_price(to_number(v), margin, tax, fee, fixed))
    return out
