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


# 🔥 CORRIGIDO AQUI
def _get_deposito():
    return st.session_state.get("deposito_nome", "")


def render_origem_mapeamento():

    df_origem = st.session_state.get("df_origem")
    df_modelo = _get_modelo()

    if df_origem is None or df_modelo is None:
        return

    st.markdown("### 🔗 Mapeamento")

    sugestoes = sugestao_automatica(df_origem, list(df_modelo.columns))

    mapping = {}

    for col in df_modelo.columns:
        mapping[col] = st.selectbox(
            col,
            [""] + list(df_origem.columns),
            index=0,
            key=f"map_{col}",
        )

    # 🔥 CRIA DF BASEADO NO MODELO
    df_saida = pd.DataFrame()

    for col in df_modelo.columns:
        origem = mapping.get(col)

        if origem and origem in df_origem.columns:
            df_saida[col] = df_origem[origem]
        else:
            # 🔥 GARANTE COLUNA EXISTENTE
            df_saida[col] = ""

    # 🔥 DEPÓSITO GARANTIDO (CORREÇÃO PRINCIPAL)
    deposito = _get_deposito()

    if deposito:
        col_dep = None

        for col in df_saida.columns:
            if "deposit" in col.lower() or "depós" in col.lower():
                col_dep = col
                break

        if col_dep:
            df_saida[col_dep] = deposito
        else:
            # 🔥 cria se não existir
            df_saida["Depósito"] = deposito

    # 🔥 PRECIFICAÇÃO
    df_saida = aplicar_precificacao_automatica(df_saida)

    st.session_state["df_saida"] = df_saida

    # 🔥 PREVIEW COLAPSADO (mantido)
    with st.expander("📦 Preview final", expanded=False):
        st.dataframe(df_saida.head(20), width="stretch")

    buffer = BytesIO()
    df_saida.to_excel(buffer, index=False)

    st.download_button(
        "⬇️ Baixar",
        buffer.getvalue(),
        "bling.xlsx",
        width="stretch",
    )
