from __future__ import annotations

import streamlit as st

from bling_app_zero.enterprise.config import get_enterprise_config


def is_authenticated() -> bool:
    return bool(st.session_state.get("user_authenticated"))


def login_panel():
    cfg = get_enterprise_config()
    if not cfg.enabled:
        return True

    if is_authenticated():
        return True

    st.title("🔐 Login")

    user = st.text_input("Usuário")
    pwd = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        # 🔥 SIMPLES (placeholder pronto para Supabase depois)
        if user and pwd:
            st.session_state["user_authenticated"] = True
            st.session_state["user_name"] = user
            st.success("Login realizado")
            st.rerun()
        else:
            st.error("Informe usuário e senha")

    return False
