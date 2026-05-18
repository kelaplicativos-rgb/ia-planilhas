from __future__ import annotations

import pandas as pd


def _columns(df: pd.DataFrame | None) -> list[str]:
    if isinstance(df, pd.DataFrame) and len(df.columns):
        return [str(column) for column in df.columns]
    return []


def cadastro_model(df_modelo: pd.DataFrame | None) -> pd.DataFrame:
    """Retorna somente a planilha modelo anexada.

    Regra global: mapeamento não pode cair em modelo padrão interno. Se não
    houver modelo anexado, retorna vazio para bloquear o fluxo corretamente.
    """
    columns = _columns(df_modelo)
    if not columns:
        return pd.DataFrame()
    return df_modelo.copy().fillna('')


def estoque_model(df_modelo: pd.DataFrame | None) -> pd.DataFrame:
    """Retorna somente a planilha modelo anexada para estoque."""
    columns = _columns(df_modelo)
    if not columns:
        return pd.DataFrame()
    return df_modelo.copy().fillna('')


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
