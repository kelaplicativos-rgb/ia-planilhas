from __future__ import annotations

import streamlit as st

from bling_app_zero.enterprise.config import get_enterprise_config
from bling_app_zero.enterprise.cloud_client import cloud_enabled, select_rows


def render_production_panel():
    with st.sidebar.expander("☁️ Produção", expanded=False):
        cfg = get_enterprise_config()

        if not cfg.enabled:
            st.warning("Enterprise desativado")
            return

        if not cloud_enabled():
            st.error("Cloud não configurado (Supabase)")
            return

        if st.button("Testar conexão"):
            ok, data = select_rows("workspaces", limit=1)
            if ok:
                st.success("Cloud OK")
            else:
                st.error(str(data))

        if st.button("Ver logs cloud"):
            ok, data = select_rows("usage_logs", limit=10)
            if ok:
                st.write(data)
            else:
                st.error(str(data))
