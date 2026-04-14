from __future__ import annotations

import streamlit as st


def get_user_key(default: str = "default") -> str:
    """
    Função neutralizada.
    Mantida apenas para compatibilidade com chamadas legadas.
    """
    try:
        valor = str(st.session_state.get("user_key") or "").strip()
        return valor or default
    except Exception:
        return default


def ensure_user_key(default: str = "default") -> str:
    """
    Função neutralizada.
    Mantida apenas para compatibilidade com chamadas legadas.
    """
    chave = get_user_key(default=default)
    st.session_state["user_key"] = chave
    return chave
