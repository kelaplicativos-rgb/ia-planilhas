from __future__ import annotations

import pandas as pd

from bling_app_zero.engines.estoque_engine import run_estoque_engine


def run_pipeline(df_source: pd.DataFrame, df_model: pd.DataFrame | None = None, deposito: str = '') -> tuple[pd.DataFrame, dict[str, str]]:
    return run_estoque_engine(df_source=df_source, df_model=df_model, deposito=deposito)
