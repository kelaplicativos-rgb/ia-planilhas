from __future__ import annotations

# Wrapper oficial do fluxo Preços Multiloja.
# A entrada visual agora fica limpa: o usuário vê diretamente Etapa 1 do fluxo
# multiloja, sem passar por telas do wizard universal ou por cabeçalhos extras.

from collections.abc import Callable

import pandas as pd

from bling_app_zero.core.global_dataset_guard import dataframe_table_signature
from bling_app_zero.v2.price_multistore.source_origin_panel import (
    get_multistore_source_origin_df,
    should_use_multistore_complementary_source,
)
from bling_app_zero.v2.price_multistore import ui as original_ui
from bling_app_zero.v2.session_store import get_state, widget_key

_ORIGINAL_READ: Callable[[object], pd.DataFrame | None] = original_ui._read
_ORIGINAL_SIGNATURE = original_ui._df_signature
SUGGESTED_PRICE_COLUMN_STATE = 'multistore_source_suggested_price_column'
SOURCE_UPLOAD_WIDGET = 'multistore_source_upload'
COST_COLUMN_WIDGET = 'multistore_cost_column'


def _patched_signature(df: pd.DataFrame | None) -> str:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return 'empty'
    return dataframe_table_signature(df, context='price_multistore')


def _patched_read_factory():
    """Cria um leitor temporário para injetar origem complementar como Planilha 2.

    O motor base chama `_read()` duas vezes: Planilha 1 do Bling e Planilha 2 de
    custo. Este patch só interfere quando não há upload da Planilha 2 e o usuário
    já escolheu usar uma origem complementar válida.
    """
    call_index = {'value': 0}

    def _patched_read(uploaded_file) -> pd.DataFrame | None:
        call_index['value'] += 1
        if uploaded_file is not None:
            return _ORIGINAL_READ(uploaded_file)
        if call_index['value'] >= 2 and should_use_multistore_complementary_source():
            source_df = get_multistore_source_origin_df()
            if isinstance(source_df, pd.DataFrame) and not source_df.empty:
                return source_df.copy().fillna('')
        return None

    return _patched_read


def _prime_cost_column_from_complementary_source(source_df: pd.DataFrame | None) -> None:
    if not should_use_multistore_complementary_source():
        return
    if not isinstance(source_df, pd.DataFrame) or source_df.empty:
        return
    suggested = str(get_state(SUGGESTED_PRICE_COLUMN_STATE) or '').strip()
    if not suggested or suggested not in [str(column) for column in source_df.columns]:
        return
    cost_key = widget_key(COST_COLUMN_WIDGET)
    source_upload_key = widget_key(SOURCE_UPLOAD_WIDGET)
    try:
        import streamlit as st

        if st.session_state.get(source_upload_key) is None:
            st.session_state[cost_key] = suggested
    except Exception:
        return


def render_price_multistore_v2() -> None:
    """Renderiza o Multiloja como fluxo próprio, sem etapas do wizard universal."""
    source_df = get_multistore_source_origin_df() if should_use_multistore_complementary_source() else None
    _prime_cost_column_from_complementary_source(source_df)

    previous_read = original_ui._read
    previous_signature = original_ui._df_signature
    original_ui._read = _patched_read_factory()
    original_ui._df_signature = _patched_signature
    try:
        original_ui.render_price_multistore_v2()
    finally:
        original_ui._read = previous_read
        original_ui._df_signature = previous_signature


__all__ = ['render_price_multistore_v2']
