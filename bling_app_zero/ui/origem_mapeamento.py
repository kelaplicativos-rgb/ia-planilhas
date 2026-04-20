
# (ARQUIVO COMPLETO REESCRITO E CONSOLIDADO)

from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    blindar_df_para_bling,
    get_etapa,
    sincronizar_etapa_global,
    safe_df_dados,
    safe_df_estrutura,
    normalizar_texto,
)

# ==============================
# CORE
# ==============================

def _garantir_etapa():
    if get_etapa() != "mapeamento":
        sincronizar_etapa_global("mapeamento")

# ==============================
# BASE
# ==============================

def _get_df_base():
    df = st.session_state.get("df_precificado")
    return df if safe_df_dados(df) else pd.DataFrame()

def _get_df_modelo():
    df = st.session_state.get("df_modelo")
    return df if safe_df_estrutura(df) else pd.DataFrame()

# ==============================
# MAPEAMENTO
# ==============================

def _init_mapping(df_modelo):
    if "mapping_manual" not in st.session_state:
        st.session_state["mapping_manual"] = {
            col: "" for col in df_modelo.columns
        }

def _validar_mapping(mapping, df_modelo):
    erros = []

    # descrição obrigatória
    if "Descrição" in df_modelo.columns:
        if not mapping.get("Descrição"):
            erros.append("Descrição obrigatória não mapeada")

    return len(erros) == 0, erros

# ==============================
# APPLY
# ==============================

def _gerar_df_final(df_base, df_modelo, mapping):
    df = pd.DataFrame(index=df_base.index)

    for col_modelo in df_modelo.columns:
        origem = mapping.get(col_modelo, "")
        if origem in df_base.columns:
            df[col_modelo] = df_base[origem]
        else:
            df[col_modelo] = ""

    df = blindar_df_para_bling(df)

    return df

# ==============================
# RENDER
# ==============================

def render_origem_mapeamento():
    _garantir_etapa()

    st.subheader("Mapeamento")

    df_base = _get_df_base()
    df_modelo = _get_df_modelo()

    if df_base.empty or df_modelo.empty:
        st.warning("Precisa de dados e modelo antes de mapear")
        return

    _init_mapping(df_modelo)

    mapping = st.session_state["mapping_manual"]

    st.markdown("### Mapeamento manual")

    for col in df_modelo.columns:
        mapping[col] = st.selectbox(
            col,
            [""] + list(df_base.columns),
            index=0,
            key=f"map_{col}"
        )

    valido, erros = _validar_mapping(mapping, df_modelo)

    if erros:
        st.warning("\n".join(erros))

    if st.button("Gerar resultado final"):
        df_final = _gerar_df_final(df_base, df_modelo, mapping)

        st.session_state["df_final"] = df_final

        st.success("DF FINAL GERADO")
        st.rerun()

    if safe_df_estrutura(st.session_state.get("df_final")):
        st.success("Resultado pronto ✔")
