from __future__ import annotations

import pandas as pd


def adapt_dataframe_to_model_contract(df: pd.DataFrame, df_model: pd.DataFrame | None) -> pd.DataFrame:
    """Adapta a saída final para ficar fiel ao modelo anexado.

    Regras:
    - se não houver modelo válido, mantém o DataFrame como está;
    - se houver modelo, a saída fica com as mesmas colunas e na mesma ordem;
    - colunas existentes são preservadas;
    - colunas ausentes ficam vazias;
    - colunas extras são removidas apenas na cópia de download.
    """
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    if not isinstance(df_model, pd.DataFrame) or not len(df_model.columns):
        return df.copy()

    out = df.copy().fillna('')
    contract_columns = [str(column) for column in df_model.columns]
    adapted = pd.DataFrame(index=out.index)
    for column in contract_columns:
        if column in out.columns:
            adapted[column] = out[column].fillna('').astype(str)
        else:
            adapted[column] = ''
    return adapted.reset_index(drop=True)


def model_for_operation(operation: str) -> pd.DataFrame | None:
    """Busca modelo salvo na sessão para preservar contrato do download."""
    import streamlit as st

    op = str(operation or '').strip().lower()
    candidate_keys: list[str]
    if op == 'estoque':
        candidate_keys = [
            'home_modelo_estoque_df',
            'df_modelo_estoque',
            'modelo_estoque_df',
        ]
    elif op == 'cadastro':
        candidate_keys = [
            'home_modelo_cadastro_df',
            'df_modelo_cadastro',
            'modelo_cadastro_df',
        ]
    else:
        candidate_keys = []

    for key in candidate_keys:
        value = st.session_state.get(key)
        if isinstance(value, pd.DataFrame) and len(value.columns):
            return value.copy().fillna('')
    return None


__all__ = ['adapt_dataframe_to_model_contract', 'model_for_operation']
