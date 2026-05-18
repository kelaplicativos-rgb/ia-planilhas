from __future__ import annotations

import pandas as pd

# Regra global atual:
# - o mapeamento e o arquivo final devem respeitar somente a planilha modelo anexada pelo usuário;
# - não existe mais fallback para modelo interno predefinido;
# - sem modelo anexado, o fluxo deve bloquear e pedir o modelo correto.

CADASTRO_BLING_COLUMNS: list[str] = []
ESTOQUE_BLING_COLUMNS: list[str] = []


def cadastro_default_model() -> pd.DataFrame:
    """Compatibilidade com imports antigos: não fornece modelo predefinido."""
    return pd.DataFrame()


def estoque_default_model() -> pd.DataFrame:
    """Compatibilidade com imports antigos: não fornece modelo predefinido."""
    return pd.DataFrame()


def model_columns(df_model: pd.DataFrame | None, operation: str) -> list[str]:
    _ = operation
    if isinstance(df_model, pd.DataFrame) and len(df_model.columns):
        return [str(column) for column in df_model.columns]
    return []


def model_for_operation(df_model: pd.DataFrame | None, operation: str) -> pd.DataFrame:
    columns = model_columns(df_model, operation)
    return pd.DataFrame(columns=columns)


def enforce_model_contract(
    df_final: pd.DataFrame | None,
    operation: str,
    df_model: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Força o CSV final a seguir somente o contrato anexado pelo usuário."""
    columns = model_columns(df_model, operation)
    if not columns:
        return pd.DataFrame()
    if not isinstance(df_final, pd.DataFrame):
        return pd.DataFrame(columns=columns)
    return df_final.copy().fillna('').reindex(columns=columns, fill_value='')


__all__ = [
    'CADASTRO_BLING_COLUMNS',
    'ESTOQUE_BLING_COLUMNS',
    'cadastro_default_model',
    'enforce_model_contract',
    'estoque_default_model',
    'model_columns',
    'model_for_operation',
]
