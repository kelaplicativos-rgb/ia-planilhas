from __future__ import annotations

import streamlit as st

from bling_app_zero.core.tenant import get_workspace_id, set_workspace_id


def render_workspace_panel():
    with st.sidebar.expander("🏢 Workspace (SaaS)", expanded=False):
        atual = get_workspace_id()

        novo = st.text_input("ID do cliente", value=atual)

        if st.button("Trocar workspace"):
            ws = set_workspace_id(novo)
            st.success(f"Workspace ativo: {ws}")
            st.rerun()

        st.caption(f"Atual: {atual}")
