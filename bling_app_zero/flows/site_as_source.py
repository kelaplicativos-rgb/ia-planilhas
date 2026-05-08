from __future__ import annotations

import pandas as pd
import streamlit as st

SITE_SOURCE_KEY = 'df_origem_site_como_planilha'
SITE_OPERATION_KEY = 'site_operation_como_planilha'
SITE_SOURCE_URLS_KEY = 'site_source_urls_como_planilha'
SITE_REQUESTED_COLUMNS_KEY = 'site_requested_columns_como_planilha'
SITE_CADASTRO_MODEL_KEY = 'site_modelo_cadastro_como_planilha'
SITE_ESTOQUE_MODEL_KEY = 'site_modelo_estoque_como_planilha'
SITE_OPERATION_MODEL_KEY = 'site_modelo_operacao_como_planilha'

PLANILHA_SOURCE_KEYS = [
    'df_origem',
    'df_origem_cadastro',
    'df_origem_planilha',
    'df_produtos_origem',
    'df_source',
]
PLANILHA_MODEL_CADASTRO_KEYS = [
    'df_modelo_cadastro',
    'modelo_cadastro_df',
]
PLANILHA_MODEL_ESTOQUE_KEYS = [
    'df_modelo_estoque',
    'modelo_estoque_df',
]


def _copy_df(df: pd.DataFrame | None) -> pd.DataFrame | None:
    if isinstance(df, pd.DataFrame) and len(df.columns):
        return df.copy().fillna('')
    return None


def _mirror_as_uploaded_planilha(
    df: pd.DataFrame,
    cadastro_model_df: pd.DataFrame | None = None,
    estoque_model_df: pd.DataFrame | None = None,
) -> None:
    """Faz a origem gerada por site aparecer como se fosse planilha anexada."""
    origem = _copy_df(df) or pd.DataFrame()
    for key in PLANILHA_SOURCE_KEYS:
        st.session_state[key] = origem.copy().fillna('')

    cadastro_model = _copy_df(cadastro_model_df)
    estoque_model = _copy_df(estoque_model_df)

    if cadastro_model is not None:
        for key in PLANILHA_MODEL_CADASTRO_KEYS:
            st.session_state[key] = cadastro_model.copy().fillna('')
    if estoque_model is not None:
        for key in PLANILHA_MODEL_ESTOQUE_KEYS:
            st.session_state[key] = estoque_model.copy().fillna('')

    st.session_state['origem_dados'] = 'planilha'
    st.session_state['origem_tipo'] = 'planilha'
    st.session_state['origem_planilha_via_site'] = True
    st.session_state['site_gerou_origem_planilha'] = True


def set_site_source_as_planilha(
    df: pd.DataFrame,
    operation: str,
    raw_urls: str,
    requested_columns: list[str] | None = None,
    cadastro_model_df: pd.DataFrame | None = None,
    estoque_model_df: pd.DataFrame | None = None,
    operation_model_df: pd.DataFrame | None = None,
) -> None:
    """Registra a captura por site como origem equivalente a uma planilha carregada."""
    st.session_state[SITE_SOURCE_KEY] = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    st.session_state[SITE_OPERATION_KEY] = operation
    st.session_state[SITE_SOURCE_URLS_KEY] = raw_urls
    st.session_state[SITE_REQUESTED_COLUMNS_KEY] = list(requested_columns or [])

    cadastro_model = _copy_df(cadastro_model_df)
    estoque_model = _copy_df(estoque_model_df)
    operation_model = _copy_df(operation_model_df)

    if cadastro_model is not None:
        st.session_state[SITE_CADASTRO_MODEL_KEY] = cadastro_model
    if estoque_model is not None:
        st.session_state[SITE_ESTOQUE_MODEL_KEY] = estoque_model
    if operation_model is not None:
        st.session_state[SITE_OPERATION_MODEL_KEY] = operation_model

    _mirror_as_uploaded_planilha(
        df=df,
        cadastro_model_df=cadastro_model or operation_model,
        estoque_model_df=estoque_model,
    )


def get_site_source_for_operation(operation: str) -> pd.DataFrame | None:
    saved_operation = st.session_state.get(SITE_OPERATION_KEY)
    df = st.session_state.get(SITE_SOURCE_KEY)
    if saved_operation != operation:
        return None
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.copy().fillna('')
    return None


def get_site_model_for_operation(operation: str) -> pd.DataFrame | None:
    if operation == 'cadastro':
        df = st.session_state.get(SITE_CADASTRO_MODEL_KEY)
        if not isinstance(df, pd.DataFrame):
            df = st.session_state.get(SITE_OPERATION_MODEL_KEY)
    elif operation == 'estoque':
        df = st.session_state.get(SITE_ESTOQUE_MODEL_KEY)
        if not isinstance(df, pd.DataFrame):
            df = st.session_state.get(SITE_OPERATION_MODEL_KEY)
    else:
        df = st.session_state.get(SITE_OPERATION_MODEL_KEY)
    return _copy_df(df) if isinstance(df, pd.DataFrame) else None


def get_site_estoque_model() -> pd.DataFrame | None:
    df = st.session_state.get(SITE_ESTOQUE_MODEL_KEY)
    return _copy_df(df) if isinstance(df, pd.DataFrame) else None


def clear_site_source() -> None:
    for key in [
        SITE_SOURCE_KEY,
        SITE_OPERATION_KEY,
        SITE_SOURCE_URLS_KEY,
        SITE_REQUESTED_COLUMNS_KEY,
        SITE_CADASTRO_MODEL_KEY,
        SITE_ESTOQUE_MODEL_KEY,
        SITE_OPERATION_MODEL_KEY,
        *PLANILHA_SOURCE_KEYS,
        *PLANILHA_MODEL_CADASTRO_KEYS,
        *PLANILHA_MODEL_ESTOQUE_KEYS,
        'origem_dados',
        'origem_tipo',
        'origem_planilha_via_site',
        'site_gerou_origem_planilha',
    ]:
        st.session_state.pop(key, None)


def has_site_source(operation: str) -> bool:
    return get_site_source_for_operation(operation) is not None
