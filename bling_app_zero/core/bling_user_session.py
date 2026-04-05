from __future__ import annotations

import re
from typing import Optional

import streamlit as st


SESSION_USER_KEY = "bling_current_user_key"
SESSION_USER_LABEL = "bling_current_user_label"


def _slugify(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9._@-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    return text.strip("-")


def normalize_user_key(value: str) -> str:
    key = _slugify(value)
    return key or "default"


def set_current_user(identifier: str, display_name: Optional[str] = None) -> str:
    user_key = normalize_user_key(identifier)
    st.session_state[SESSION_USER_KEY] = user_key
    st.session_state[SESSION_USER_LABEL] = (display_name or identifier or user_key).strip()
    return user_key


def get_current_user_key() -> str:
    return normalize_user_key(str(st.session_state.get(SESSION_USER_KEY, "default")))


def get_current_user_label() -> str:
    label = str(st.session_state.get(SESSION_USER_LABEL, "")).strip()
    return label or get_current_user_key()


def ensure_current_user_defaults() -> None:
    if SESSION_USER_KEY not in st.session_state:
        st.session_state[SESSION_USER_KEY] = "default"
    if SESSION_USER_LABEL not in st.session_state:
        st.session_state[SESSION_USER_LABEL] = "Operação padrão"
