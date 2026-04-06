from __future__ import annotations

from io import BytesIO
import pandas as pd
import streamlit as st


def _get_modelo():
    if st.session_state.get("tipo_operacao_bling") == "cadastro":
        return st.session_state.get("df_modelo_cadastro")
    return st.session_state.get("df_modelo_estoque")


def _get_deposito():
    return st.session_state.get("deposito_nome", "")


# 🔥 DETECTORES
def _is_coluna_deposito(nome):
    nome = str(nome).lower()
    return "deposit" in nome or "depós" in nome


def _is_coluna_preco(nome):
    nome = str(nome).lower()
    return "preço" in nome or "preco" in nome


def render_origem_mapeamento():

    df_origem = st.session_state.get("df_origem")
    df_modelo = _get_modelo()
    df_preparado = st.session_state.get("df_saida")  # 🔥 já vem com preço e depósito

    if df_origem is None or df_modelo is None:
        return

    st.markdown("### 🔗 Mapeamento")

    deposito = _get_deposito()
    bloqueios = st.session_state.get("bloquear_campos_auto", {})

    mapping = {}

    # =========================
    # 🔥 UI MAIS COMPACTA (MOBILE)
    # =========================
    colunas = list(df_modelo.columns)

    for i in range(0, len(colunas), 2):
        cols = st.columns(2)

        for j in range(2):
            if i + j >= len(colunas):
                continue

            col = colunas[i + j]

            with cols[j]:

                # 🔒 DEPÓSITO
                if _is_coluna_deposito(col) and deposito:
                    st.text_input(col, value=deposito, disabled=True)
                    mapping[col] = None
                    continue

                # 🔒 PREÇO
                if _is_coluna_preco(col) and bloqueios.get("preco"):
                    st.text_input(col, value="Calculado automaticamente", disabled=True)
                    mapping[col] = None
                    continue

                # 🔥 NORMAL
                mapping[col] = st.selectbox(
                    col,
                    [""] + list(df_origem.columns),
                    index=0,
                    key=f"map_{col}",
                )

    # =========================
    # 🔥 MONTA DF FINAL
    # =========================
    df_saida = pd.DataFrame()

    for col in df_modelo.columns:

        origem = mapping.get(col)

        # 🔥 PRIORIDADE → DADOS JÁ PREPARADOS (PREÇO / DEPÓSITO)
        if df_preparado is not None and col in df_preparado.columns:
            if _is_coluna_preco(col) or _is_coluna_deposito(col):
                df_saida[col] = df_preparado[col]
                continue

        # 🔥 MAPEAMENTO NORMAL
        if origem and origem in df_origem.columns:
            df_saida[col] = df_origem[origem]
        else:
            df_saida[col] = ""

    # =========================
    # 🔥 GARANTE DEPÓSITO
    # =========================
    if deposito:
        col_dep = None

        for col in df_saida.columns:
            if _is_coluna_deposito(col):
                col_dep = col
                break

        if col_dep:
            df_saida[col_dep] = deposito
        else:
            df_saida["Depósito"] = deposito

    # 🔥 NÃO RECALCULA PREÇO AQUI (JÁ VEIO PRONTO)

    st.session_state["df_saida"] = df_saida

    # =========================
    # 🔥 PREVIEW
    # =========================
    with st.expander("📦 Preview final", expanded=False):
        st.dataframe(df_saida.head(20), width="stretch")

    # =========================
    # 🔥 DOWNLOAD
    # =========================
    buffer = BytesIO()
    df_saida.to_excel(buffer, index=False)

    st.download_button(
        "⬇️ Baixar",
        buffer.getvalue(),
        "bling.xlsx",
        use_container_width=True,
    )
