from __future__ import annotations

import pandas as pd
import streamlit as st

SITE_SOURCE_KEY = 'df_origem_site_como_planilha'
SITE_OPERATION_KEY = 'site_operation_como_planilha'
SITE_SOURCE_URLS_KEY = 'site_source_urls_como_planilha'
SITE_REQUESTED_COLUMNS_KEY = 'site_requested_columns_como_planilha'


def set_site_source_as_planilha(
    df: pd.DataFrame,
    operation: str,
    raw_urls: str,
    requested_columns: list[str] | None = None,
) -> None:
    """Registra a captura por site como origem equivalente a uma planilha carregada."""
    st.session_state[SITE_SOURCE_KEY] = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    st.session_state[SITE_OPERATION_KEY] = operation
    st.session_state[SITE_SOURCE_URLS_KEY] = raw_urls
    st.session_state[SITE_REQUESTED_COLUMNS_KEY] = list(requested_columns or [])


def get_site_source_for_operation(operation: str) -> pd.DataFrame | None:
    saved_operation = st.session_state.get(SITE_OPERATION_KEY)
    df = st.session_state.get(SITE_SOURCE_KEY)
    if saved_operation != operation:
        return None
    if isinstance(df, pd.DataFrame) and not df.empty:
        return df.copy().fillna('')
    return None


def clear_site_source() -> None:
    for key in [SITE_SOURCE_KEY, SITE_OPERATION_KEY, SITE_SOURCE_URLS_KEY, SITE_REQUESTED_COLUMNS_KEY]:
        st.session_state.pop(key, None)


def has_site_source(operation: str) -> bool:
    return get_site_source_for_operation(operation) is not None
