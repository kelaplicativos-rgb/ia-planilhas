from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.user_bling_models_store import MODEL_TYPES


def render_modelos_bling_user_screen() -> None:
    st.markdown('### Bling')
    st.info('Tela de modelos base do usuario.')
    st.write(MODEL_TYPES)


__all__ = ['render_modelos_bling_user_screen']
