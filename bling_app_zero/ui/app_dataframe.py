
from __future__ import annotations

from typing import Any

import pandas as pd


def safe_df(df: Any) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df.copy()
    return pd.DataFrame()


def safe_df_dados(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty and len(df.columns) > 0


def safe_df_estrutura(df: Any) -> bool:
    return isinstance(df, pd.DataFrame) and len(df.columns) > 0


def garantir_dataframe(df: Any) -> pd.DataFrame:
    if isinstance(df, pd.DataFrame):
        return df.copy()
    return pd.DataFrame()
