from __future__ import annotations

import streamlit as st

from .app_core_config import APP_DEFAULTS


def init_state():
    for k, v in APP_DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v
