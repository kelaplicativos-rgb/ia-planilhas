from __future__ import annotations

from io import BytesIO
import pandas as pd
import streamlit as st

from bling_app_zero.core.precificacao import aplicar_precificacao_automatica
from bling_app_zero.core.mapeamento_auto import sugestao_automatica


def _get_modelo():
    if st.session_state.get("tipo_operacao_bling") == "cadastro":
        return st.session_state.get("df_modelo_cadastro")
    return st.session_state.get("df_modelo_estoque")


def _get_deposito():
    return st.session_state.get("deposito_nome_manual", "")


def render_origem_mapeamento():

    df_origem = st.session_state.get("df_origem")
    df_modelo = _get_modelo()

    if df_origem is None or df_modelo is None:
        return

    st.markdown("### 🔗 Mapeamento")

    sugestoes = sugestao_automatica(df_origem, list(df_modelo.columns))

    mapping = {}

    # 🔥 layout compacto (mobile)
    for col in df_modelo.columns:
        mapping[col] = st.selectbox(
            col,
            [""] + list(df_origem.columns),
            index=0,
            key=f"map_{col}",
        )

    # 🔥 montar DF
    df_saida = pd.DataFrame(columns=df_modelo.columns)

    for col in df_modelo.columns:
        origem = mapping.get(col)
        if origem and origem in df_origem.columns:
            df_saida[col] = df_origem[origem]

    # 🔥 depósito FORÇADO
    deposito = _get_deposito()
    if deposito:
        for col in df_saida.columns:
            if "deposito" in col.lower():
                df_saida[col] = deposito

    # 🔥 PRECIFICAÇÃO AUTOMÁTICA
    df_saida = aplicar_precificacao_automatica(df_saida)

    st.session_state["df_saida"] = df_saida

    # 🔥 PREVIEW FINAL (COLAPSADO)
    with st.expander("📦 Preview final", expanded=False):
        st.dataframe(df_saida.head(20), width="stretch")

    # DOWNLOAD
    buffer = BytesIO()
    df_saida.to_excel(buffer, index=False)

    st.download_button(
        "⬇️ Baixar",
        buffer.getvalue(),
        "bling.xlsx",
        width="stretch",
    )
