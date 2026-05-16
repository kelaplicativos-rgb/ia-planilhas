from __future__ import annotations

import pandas as pd

from bling_app_zero.universal.universal_contract import UniversalContract, build_universal_contract, validate_universal_output


def _safe_series(df_source: pd.DataFrame, source_column: str, length: int) -> pd.Series:
    if isinstance(df_source, pd.DataFrame) and source_column in df_source.columns:
        return df_source[source_column].fillna('').astype(str).reset_index(drop=True)
    return pd.Series([''] * length, dtype='object')


def build_universal_output(
    df_source: pd.DataFrame,
    df_model: pd.DataFrame,
    mapping: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Gera saída idêntica ao modelo anexado.

    Regra central do MapeiaAI:
    - mesmas colunas do modelo;
    - mesma ordem do modelo;
    - sem colunas extras;
    - coluna não encontrada fica vazia;
    - mapeamento origem -> destino preenche quando existir.
    """
    contract = build_universal_contract(df_model)
    source = df_source if isinstance(df_source, pd.DataFrame) else pd.DataFrame()
    length = int(len(source)) if not source.empty else 0
    data: dict[str, pd.Series] = {}
    safe_mapping = mapping or {}

    for target_column in contract.columns:
        source_column = str(safe_mapping.get(target_column, '') or '')
        data[target_column] = _safe_series(source, source_column, length)

    df_output = pd.DataFrame(data, columns=contract.columns)
    errors = validate_universal_output(df_output, contract)
    if errors:
        raise ValueError(' | '.join(errors))
    return df_output


def empty_universal_output(df_model: pd.DataFrame, rows: int = 0) -> pd.DataFrame:
    contract: UniversalContract = build_universal_contract(df_model)
    rows = max(0, int(rows or 0))
    return pd.DataFrame({column: [''] * rows for column in contract.columns}, columns=contract.columns)


__all__ = ['build_universal_output', 'empty_universal_output']
