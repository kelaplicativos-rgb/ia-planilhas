from __future__ import annotations

import os

import streamlit as st


def technical_mode_enabled() -> bool:
    try:
        raw = st.secrets.get("ui", {}).get("technical_mode", False)
    except Exception:
        raw = os.getenv("UI_TECHNICAL_MODE", "false")
    return str(raw).lower() in {"1", "true", "yes", "sim"}
