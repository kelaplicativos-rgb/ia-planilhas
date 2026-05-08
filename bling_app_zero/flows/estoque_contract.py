from __future__ import annotations

import pandas as pd

DEFAULT_ESTOQUE_COLUMNS = [
    'Código',
    'Descrição',
    'Preço unitário (OBRIGATÓRIO)',
    'Depósito (OBRIGATÓRIO)',
    'Balanço (OBRIGATÓRIO)',
]


def default_model() -> pd.DataFrame:
    return pd.DataFrame(columns=DEFAULT_ESTOQUE_COLUMNS)


def requested_columns_from_model(df_model: pd.DataFrame | None) -> list[str]:
    if isinstance(df_model, pd.DataFrame) and len(df_model.columns):
        return [str(column) for column in df_model.columns]
    return list(DEFAULT_ESTOQUE_COLUMNS)
