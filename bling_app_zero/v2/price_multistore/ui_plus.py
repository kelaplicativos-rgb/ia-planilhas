from __future__ import annotations

from collections.abc import Callable

import pandas as pd
import streamlit as st

from bling_app_zero.v2.price_multistore.source_origin_panel import get_multistore_source_origin_df, render_multistore_source_origin_panel
from bling_app_zero.v2.price_multistore import ui as original_ui


_ORIGINAL_READ: Callable[[object], pd.DataFrame | None] = original_ui._read


def _patched_read_factory():
    call_index = {'value': 0}

    def _patched_read(uploaded_file) -> pd.DataFrame | None:
        call_index['value'] += 1
        if uploaded_file is not None:
            return _ORIGINAL_READ(uploaded_file)
        if call_index['value'] >= 2:
            source_df = get_multistore_source_origin_df()
            if isinstance(source_df, pd.DataFrame) and not source_df.empty:
                return source_df.copy().fillna('')
        return None

    return _patched_read


def render_price_multistore_v2() -> None:
    st.markdown('### Origem complementar')
    source_df = render_multistore_source_origin_panel()
    if isinstance(source_df, pd.DataFrame) and not source_df.empty:
        st.caption('A origem complementar está ativa e será usada como Planilha 2 se nenhum upload manual for enviado.')
    st.divider()

    previous_read = original_ui._read
    original_ui._read = _patched_read_factory()
    try:
        original_ui.render_price_multistore_v2()
    finally:
        original_ui._read = previous_read


__all__ = ['render_price_multistore_v2']
