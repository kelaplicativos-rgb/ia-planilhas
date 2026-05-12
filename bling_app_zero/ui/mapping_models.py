from __future__ import annotations

import pandas as pd

from bling_app_zero.engines.cadastro_engine import default_model
from bling_app_zero.flows.estoque_contract import default_model as estoque_default_model


def cadastro_model(df_modelo: pd.DataFrame | None) -> pd.DataFrame:
    if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns):
        return df_modelo
    return default_model()


def estoque_model(df_modelo: pd.DataFrame | None) -> pd.DataFrame:
    if isinstance(df_modelo, pd.DataFrame) and len(df_modelo.columns):
        return df_modelo
    return estoque_default_model()


def source_columns_from_df(df_source: pd.DataFrame) -> list[str]:
    return [str(column) for column in df_source.columns]


def target_columns_from_model(model: pd.DataFrame) -> list[str]:
    return [str(column) for column in model.columns]


__all__ = [
    'cadastro_model',
    'estoque_model',
    'source_columns_from_df',
    'target_columns_from_model',
]
