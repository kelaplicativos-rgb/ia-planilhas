from __future__ import annotations

import pandas as pd

from bling_app_zero.universal.model_contract_detector import MODEL_CONTRACT_TYPE_KEY, normalize_contract_operation


def adapt_dataframe_to_model_contract(df: pd.DataFrame, df_model: pd.DataFrame | None) -> pd.DataFrame:
    """Adapta a saída final para ficar fiel ao modelo anexado."""
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


def _first_valid_model_from_session(candidate_keys: list[str]) -> pd.DataFrame | None:
    import streamlit as st

    for key in candidate_keys:
        value = st.session_state.get(key)
        if isinstance(value, pd.DataFrame) and len(value.columns):
            return value.copy().fillna('')
    return None


def _resolved_operation(operation: str) -> str:
    import streamlit as st

    op = normalize_contract_operation(operation)
    if op:
        return op
    detected = normalize_contract_operation(st.session_state.get(MODEL_CONTRACT_TYPE_KEY))
    return detected or 'universal'


def model_for_operation(operation: str) -> pd.DataFrame | None:
    """Busca modelo salvo na sessão para preservar contrato real no download."""
    op = _resolved_operation(operation)

    universal_keys = [
        'home_modelo_universal_df',
        'df_modelo_universal',
        'modelo_universal_df',
        'mapeiaai_universal_model_df',
        'home_modelo_cadastro_df',
        'home_modelo_estoque_df',
        'home_modelo_atualizacao_preco_df',
        'df_modelo_cadastro',
        'df_modelo_estoque',
        'df_modelo_atualizacao_preco',
        'modelo_cadastro_df',
        'modelo_estoque_df',
        'modelo_atualizacao_preco_df',
        'cadastro_wizard_df_modelo',
        'cadastro_wizard_df_modelo_estoque',
        'estoque_wizard_df_modelo',
    ]

    if op == 'estoque':
        return _first_valid_model_from_session([
            'home_modelo_estoque_df',
            'df_modelo_estoque',
            'modelo_estoque_df',
            'cadastro_wizard_df_modelo_estoque',
            'estoque_wizard_df_modelo',
            *universal_keys,
        ])

    if op == 'atualizacao_preco':
        return _first_valid_model_from_session([
            'home_modelo_atualizacao_preco_df',
            'df_modelo_atualizacao_preco',
            'modelo_atualizacao_preco_df',
            'cadastro_wizard_df_modelo',
            *universal_keys,
        ])

    if op == 'cadastro':
        return _first_valid_model_from_session([
            'home_modelo_cadastro_df',
            'df_modelo_cadastro',
            'modelo_cadastro_df',
            'cadastro_wizard_df_modelo',
            *universal_keys,
        ])

    return _first_valid_model_from_session(universal_keys)


__all__ = ['adapt_dataframe_to_model_contract', 'model_for_operation']
