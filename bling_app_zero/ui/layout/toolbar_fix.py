from __future__ import annotations

import streamlit as st


def inject_streamlit_toolbar_fix() -> None:
    """Mantem visiveis menu superior, tres pontinhos e controle da sidebar."""
    st.markdown(
        """
        <style>
        header[data-testid="stHeader"],
        header[data-testid="stHeader"] *,
        div[data-testid="stToolbar"],
        div[data-testid="stToolbar"] *,
        div[data-testid="stDecoration"],
        div[data-testid="stStatusWidget"],
        #MainMenu,
        section[data-testid="stSidebar"],
        section[data-testid="stSidebar"] * {
            visibility: visible !important;
            opacity: 1 !important;
            pointer-events: auto !important;
        }

        header[data-testid="stHeader"] {
            display: block !important;
            z-index: 999999 !important;
            overflow: visible !important;
        }

        #MainMenu {
            display: block !important;
        }

        section[data-testid="stSidebar"] {
            z-index: 1000002 !important;
            overflow: visible !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


__all__ = ['inject_streamlit_toolbar_fix']
