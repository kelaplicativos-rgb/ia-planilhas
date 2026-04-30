from __future__ import annotations

import pandas as pd
import streamlit as st


def _nome_preset(preset) -> str:
    nome = getattr(preset, "nome", "")
    nome = str(nome or "").strip()
    return nome or "AUTO_TOTAL"


def guardar_resultado(df: pd.DataFrame, urls, preset, motor):
    base = df.copy().fillna("") if isinstance(df, pd.DataFrame) else pd.DataFrame()

    st.session_state["df_origem"] = base
    st.session_state["df_saida"] = base.copy()

    st.session_state["origem_site_urls"] = urls
    st.session_state["origem_site_total_produtos"] = len(base)
    st.session_state["origem_site_config"] = {
        "preset": _nome_preset(preset),
        "motor": str(motor or "AUTO_TOTAL"),
    }


def limpar_busca_site():
    for key in [
        "df_origem",
        "df_saida",
        "origem_site_urls",
        "origem_site_total_produtos",
        "origem_site_config",
    ]:
        st.session_state.pop(key, None)
