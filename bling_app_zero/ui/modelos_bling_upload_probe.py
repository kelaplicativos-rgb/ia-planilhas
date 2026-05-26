from __future__ import annotations

import streamlit as st


def render_probe() -> None:
    st.file_uploader('Arquivo', type=['csv'])


__all__ = ['render_probe']
