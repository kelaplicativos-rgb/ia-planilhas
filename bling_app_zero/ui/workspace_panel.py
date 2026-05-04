from __future__ import annotations

import streamlit as st

from bling_app_zero.core.tenant import get_workspace_id, set_workspace_id


def render_workspace_panel():
    st.sidebar.markdown("---")
    st.sidebar.subheader("🏢 Workspace (SaaS)")

    atual = get_workspace_id()

    novo = st.sidebar.text_input("ID do cliente", value=atual)

    if st.sidebar.button("Trocar workspace"):
        ws = set_workspace_id(novo)
        st.sidebar.success(f"Workspace ativo: {ws}")
        st.rerun()

    st.sidebar.caption(f"Atual: {atual}")
