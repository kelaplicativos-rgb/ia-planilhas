from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class ModelFidelityReport:
    ok: bool
    errors: list[str]
    model_columns: list[str]
    output_columns: list[str]


def _columns(df: pd.DataFrame | None) -> list[str]:
    if not isinstance(df, pd.DataFrame):
        return []
    return [str(column) for column in df.columns]


def assert_same_model_contract(df_model: pd.DataFrame | None, df_output: pd.DataFrame | None) -> ModelFidelityReport:
    """Garante o lema do sistema: saída com o mesmo contrato do modelo anexado.

    O sistema pode preencher valores, mas nunca pode inventar, remover, renomear
    ou reordenar colunas. Isso vale para qualquer marketplace, fornecedor,
    planilha do Bling, planilha de vínculo, preço, estoque, cadastro ou layout
    personalizado.
    """
    model_columns = _columns(df_model)
    output_columns = _columns(df_output)
    errors: list[str] = []

    if not model_columns:
        errors.append('Modelo anexado sem colunas; não há contrato para preservar.')
    if output_columns != model_columns:
        errors.append('Saída final não está idêntica ao modelo anexado em colunas e ordem.')
        missing = [column for column in model_columns if column not in output_columns]
        extra = [column for column in output_columns if column not in model_columns]
        if missing:
            errors.append('Colunas do modelo ausentes na saída: ' + ', '.join(missing))
        if extra:
            errors.append('Colunas extras proibidas na saída: ' + ', '.join(extra))

    return ModelFidelityReport(not errors, errors, model_columns, output_columns)


def enforce_same_model_contract(df_model: pd.DataFrame | None, df_output: pd.DataFrame | None) -> pd.DataFrame:
    report = assert_same_model_contract(df_model, df_output)
    if not report.ok:
        raise ValueError(' | '.join(report.errors))
    return df_output.copy() if isinstance(df_output, pd.DataFrame) else pd.DataFrame(columns=report.model_columns)


def reindex_exact_model_columns(df_output: pd.DataFrame | None, model_columns: Iterable[str]) -> pd.DataFrame:
    columns = [str(column) for column in model_columns]
    if not isinstance(df_output, pd.DataFrame):
        return pd.DataFrame(columns=columns)
    return df_output.reindex(columns=columns, fill_value='').fillna('')


__all__ = [
    'ModelFidelityReport',
    'assert_same_model_contract',
    'enforce_same_model_contract',
    'reindex_exact_model_columns',
]
