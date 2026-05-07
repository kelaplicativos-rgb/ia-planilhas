from __future__ import annotations

from typing import Any

import pandas as pd


def to_number(value: Any) -> float:
    text = str(value or '').strip()
    if not text:
        return 0.0
    text = text.replace('R$', '').replace('%', '').replace(' ', '')
    if ',' in text and '.' in text:
        text = text.replace('.', '').replace(',', '.')
    elif ',' in text:
        text = text.replace(',', '.')
    try:
        return float(text)
    except Exception:
        return 0.0


def normalize_percent(value: Any) -> float:
    number = to_number(value)
    if 0 < number <= 1:
        return number * 100.0
    return number


def calculate_price(
    cost: float,
    margin: float = 0.0,
    tax: float = 0.0,
    fee: float = 0.0,
    fixed: float = 0.0,
    discount: float = 0.0,
) -> float:
    base = float(cost or 0.0) + float(fixed or 0.0)
    total_percent = (
        float(margin or 0.0)
        + float(tax or 0.0)
        + float(fee or 0.0)
        + float(discount or 0.0)
    )

    if total_percent <= 0:
        return round(base, 2)

    if total_percent >= 95:
        total_percent = 95.0

    divisor = 1 - (total_percent / 100.0)
    return round(base / divisor, 2)


def apply_pricing(
    df: pd.DataFrame,
    cost_column: str,
    output_column: str,
    margin: float = 0.0,
    tax: float = 0.0,
    fee: float = 0.0,
    fixed: float = 0.0,
    discount: float = 0.0,
) -> pd.DataFrame:
    if df is None or not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    if df.empty or cost_column not in df.columns:
        return df.copy()
    out = df.copy().fillna('')
    out[output_column] = out[cost_column].apply(
        lambda v: calculate_price(to_number(v), margin, tax, fee, fixed, discount)
    )
    return out


def detect_discount_percent(df: pd.DataFrame | None) -> float:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return 0.0

    columns = {str(column).strip().lower(): column for column in df.columns}

    for key, original_column in columns.items():
        if 'comiss' in key and '%' in key:
            series = df[original_column].dropna()
            if not series.empty:
                values = [normalize_percent(value) for value in series.tolist()]
                values = [value for value in values if value > 0]
                if values:
                    return round(max(set(values), key=values.count), 2)

    for key, original_column in columns.items():
        if 'desconto' in key and '%' in key:
            series = df[original_column].dropna()
            if not series.empty:
                values = [normalize_percent(value) for value in series.tolist()]
                values = [value for value in values if value > 0]
                if values:
                    return round(max(set(values), key=values.count), 2)

    return 0.0
