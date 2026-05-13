from __future__ import annotations

import pandas as pd
import streamlit as st

SITE_SOURCE_KEYS = (
    'df_site_bruto_cadastro',
    'df_site_bruto_precos',
    'df_site_bruto',
)

PRICE_HINTS = (
    'preço de custo',
    'preco de custo',
    'custo',
    'valor custo',
    'valor compra',
    'preço compra',
    'preco compra',
    'preço',
    'preco',
    'price',
    'valor',
)


def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    return df.copy().fillna('').astype(str) if isinstance(df, pd.DataFrame) else pd.DataFrame()


def get_site_capture_source_df() -> tuple[pd.DataFrame | None, str]:
    """Return the latest site capture usable as multistore price source.

    The multistore price flow needs a source/cost table. When the user has just
    captured products from a supplier site, that capture should be available as
    Planilha 2 instead of forcing another upload.
    """
    for key in SITE_SOURCE_KEYS:
        value = st.session_state.get(key)
        if isinstance(value, pd.DataFrame) and not value.empty:
            return _clean_df(value), key
    return None, ''


def has_site_capture_source() -> bool:
    df, _ = get_site_capture_source_df()
    return isinstance(df, pd.DataFrame) and not df.empty


def suggest_price_column(df: pd.DataFrame | None) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return ''
    columns = [str(column) for column in df.columns]
    for hint in PRICE_HINTS:
        for column in columns:
            if hint in column.lower():
                return column
    return ''


def source_origin_label(source_key: str) -> str:
    if source_key == 'df_site_bruto_cadastro':
        return 'captura por site de cadastro'
    if source_key == 'df_site_bruto_precos':
        return 'captura por site de preços'
    if source_key == 'df_site_bruto':
        return 'última captura por site'
    return 'captura por site'


__all__ = [
    'get_site_capture_source_df',
    'has_site_capture_source',
    'source_origin_label',
    'suggest_price_column',
]
