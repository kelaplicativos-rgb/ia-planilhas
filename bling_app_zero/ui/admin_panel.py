from __future__ import annotations

import streamlit as st

from bling_app_zero.core.saas_store import read_json
from bling_app_zero.core.tenant import get_workspace_id


def render_admin_panel():
    with st.sidebar.expander("📊 Admin SaaS", expanded=False):
        ws = get_workspace_id()

        if st.button("Ver uso"):
            usage = read_json("usage.json", [], ws)
            st.write(f"Eventos: {len(usage)}")

        if st.button("Ver memória mapeamento"):
            mem = read_json("auto_map_memory.json", {}, ws)
            st.write(mem)
