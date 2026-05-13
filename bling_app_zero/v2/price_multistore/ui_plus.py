from __future__ import annotations

import streamlit as st

from bling_app_zero.v2.price_multistore.source_origin_panel import render_multistore_source_origin_panel
from bling_app_zero.v2.price_multistore.ui import render_price_multistore_v2 as render_original


def render_price_multistore_v2() -> None:
    st.markdown('### Origem complementar')
    render_multistore_source_origin_panel()
    st.divider()
    render_original()


__all__ = ['render_price_multistore_v2']
