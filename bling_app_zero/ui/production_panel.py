from __future__ import annotations

import streamlit as st

from bling_app_zero.enterprise.config import get_enterprise_config
from bling_app_zero.enterprise.cloud_client import cloud_enabled, select_rows


def render_production_panel():
    st.sidebar.markdown("---")
    st.sidebar.subheader("☁️ Produção")

    cfg = get_enterprise_config()

    if not cfg.enabled:
        st.sidebar.warning("Enterprise desativado")
        return

    if not cloud_enabled():
        st.sidebar.error("Cloud não configurado (Supabase)")
        return

    if st.sidebar.button("Testar conexão"):
        ok, data = select_rows("workspaces", limit=1)
        if ok:
            st.sidebar.success("Cloud OK")
        else:
            st.sidebar.error(str(data))

    if st.sidebar.button("Ver logs cloud"):
        ok, data = select_rows("usage_logs", limit=10)
        if ok:
            st.sidebar.write(data)
        else:
            st.sidebar.error(str(data))
