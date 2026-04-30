# bling_app_zero/ui/origem_site_panel.py

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.instant_scraper.flow_contract import (
    criar_estado_inicial,
    atualizar_status,
    registrar_html,
    registrar_candidatos,
    registrar_produtos,
)
from bling_app_zero.ui.instant_flow_panel import render_instant_flow

from bling_app_zero.core.instant_scraper.runner import run_scraper


def _txt(v: Any) -> str:
    return str(v or "").strip()


def render_origem_site_panel() -> None:
    st.markdown("#### 🚀 Busca Inteligente (Instant Scraper)")

    url = st.text_input("URL do fornecedor")

    if "instant_state" not in st.session_state:
        st.session_state["instant_state"] = criar_estado_inicial(url)

    state = st.session_state["instant_state"]

    render_instant_flow(state)

    if st.button("🔍 Buscar produtos"):
        try:
            atualizar_status(state, "carregando_html")

            df = run_scraper(url)

            atualizar_status(state, "concluido")
            registrar_produtos(state, len(df))

            st.session_state["df_origem"] = df

        except Exception as e:
            atualizar_status(state, "erro", str(e))

    df = st.session_state.get("df_origem")

    if isinstance(df, pd.DataFrame) and not df.empty:
        st.dataframe(df.head(50))
