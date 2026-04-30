from __future__ import annotations

import streamlit as st
import pandas as pd


def guardar_resultado(df: pd.DataFrame, urls, preset, motor):
    st.session_state["df_origem"] = df
    st.session_state["df_saida"] = df.copy()

    st.session_state["origem_site_urls"] = urls
    st.session_state["origem_site_total_produtos"] = len(df)
    st.session_state["origem_site_config"] = {
        "preset": preset.nome,
        "motor": motor,
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
