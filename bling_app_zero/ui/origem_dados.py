from __future__ import annotations

import hashlib
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_auto import sugestao_automatica
from bling_app_zero.core.precificacao import calcular_preco_compra_automatico_df


# ==========================================================
# HELPERS
# ==========================================================
def _hash_df(df: pd.DataFrame) -> str:
    return hashlib.md5(
        pd.util.hash_pandas_object(df, index=True).values.tobytes()
    ).hexdigest()


def _exportar_df_exato_para_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buffer.seek(0)
    return buffer.read()


def _safe_preview(df: pd.DataFrame, rows: int = 20) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    return df.head(rows)


# ==========================================================
# MAIN UI
# ==========================================================
def render_origem_dados() -> None:
    st.subheader("Origem dos dados")

    origem = st.selectbox(
        "Selecione a origem",
        ["Planilha", "XML", "Site"],
        key="origem_tipo",
    )

    df_origem = None

    # =========================
    # INPUT
    # =========================
    if origem == "Planilha":
        arquivo = st.file_uploader("Envie a planilha", type=["xlsx", "csv"])
        if arquivo:
            try:
                df_origem = pd.read_excel(arquivo)
            except Exception as e:
                st.error(f"Erro ao ler planilha: {e}")
                return

    elif origem == "XML":
        arquivo = st.file_uploader("Envie o XML", type=["xml"])
        if arquivo:
            st.warning("Leitura de XML em processamento...")
            return

    elif origem == "Site":
        url = st.text_input("URL do site")
        if url:
            st.info("Captura do site em processamento...")
            return

    if df_origem is None or df_origem.empty:
        return

    origem_hash = _hash_df(df_origem)

    # =========================
    # MODO
    # =========================
    modo = st.radio(
        "Selecione a operação",
        ["cadastro", "estoque"],
        horizontal=True,
    )

    # =========================
    # MODELOS
    # =========================
    modelo_cadastro = st.file_uploader("Modelo Cadastro", type=["xlsx"])
    modelo_estoque = st.file_uploader("Modelo Estoque", type=["xlsx"])

    if modo == "cadastro" and modelo_cadastro:
        df_modelo = pd.read_excel(modelo_cadastro)
    elif modo == "estoque" and modelo_estoque:
        df_modelo = pd.read_excel(modelo_estoque)
    else:
        st.warning("Anexe o modelo correspondente.")
        return

    colunas_modelo_ativas = list(df_modelo.columns)

    # =========================
    # MAPEAMENTO
    # =========================
    sugestoes = sugestao_automatica(df_origem, colunas_modelo_ativas)

    if "mapeamento_manual" not in st.session_state:
        st.session_state["mapeamento_manual"] = sugestoes or {}

    mapa = st.session_state["mapeamento_manual"]

    st.markdown("### Preview origem")
    st.dataframe(_safe_preview(df_origem), width="stretch")

    st.markdown("### Mapeamento")

    opcoes = [""] + list(df_origem.columns)

    for col in colunas_modelo_ativas:
        valor = mapa.get(col, "")
        if valor not in opcoes:
            valor = ""

        mapa[col] = st.selectbox(
            col,
            opcoes,
            index=opcoes.index(valor),
            key=f"map_{col}",
        )

    # =========================
    # ESTOQUE
    # =========================
    deposito = ""
    if modo == "estoque":
        deposito = st.text_input("Nome do depósito")

    # =========================
    # MONTAGEM
    # =========================
    def montar_df():
        df_saida = pd.DataFrame()

        for col in colunas_modelo_ativas:
            origem_col = mapa.get(col)

            if origem_col and origem_col in df_origem.columns:
                df_saida[col] = df_origem[origem_col]
            else:
                df_saida[col] = ""

        if modo == "estoque" and "Depósito" in df_saida.columns:
            df_saida["Depósito"] = deposito

        return df_saida

    st.divider()
    st.markdown("### Preview saída")

    df_preview = montar_df()
    st.dataframe(_safe_preview(df_preview), width="stretch")

    # =========================
    # BOTÃO
    # =========================
    if st.button("Gerar arquivo", width="stretch"):
        try:
            df_final = montar_df()
            excel = _exportar_df_exato_para_excel_bytes(df_final)

            nome = "cadastro.xlsx" if modo == "cadastro" else "estoque.xlsx"

            st.download_button(
                "Baixar",
                data=excel,
                file_name=nome,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )

            st.success("Arquivo gerado com sucesso")

        except Exception as e:
            st.error(f"Erro ao gerar: {e}")
