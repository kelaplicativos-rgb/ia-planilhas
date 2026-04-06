from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.origem_dados_helpers import (
    log_debug,
    ler_planilha_segura,
)
from bling_app_zero.ui.origem_dados_site import render_origem_site


def _safe_df_dados(df):
    try:
        if df is None:
            return None
        if len(df.columns) == 0:
            return None
        if df.empty:
            return None
        return df
    except Exception:
        return None


def _safe_df_modelo(df):
    try:
        if df is None:
            return None
        if len(df.columns) == 0:
            return None
        return df
    except Exception:
        return None


def render_origem_dados() -> None:

    if st.session_state.get("etapa_origem") == "mapeamento":
        return

    st.subheader("Origem dos dados")

    origem = st.selectbox(
        "Selecione a origem",
        ["Planilha", "XML", "Site"],
        key="origem_tipo",
    )

    df_origem = None

    if origem == "Planilha":
        arquivo = st.file_uploader(
            "Envie a planilha",
            type=["xlsx", "xls", "csv", "xlsm", "xlsb"],
            key="upload_planilha_origem",
        )

        if arquivo:
            df_origem = ler_planilha_segura(arquivo)

            if _safe_df_dados(df_origem) is None:
                st.error("Erro ao ler planilha")
                return

    elif origem == "Site":
        df_origem = render_origem_site()

    if _safe_df_dados(df_origem) is None:
        return

    st.session_state["df_origem"] = df_origem

    # 🔥 PREVIEW COM EXPANDER (FECHADO)
    with st.expander("👁️ Pré-visualização dos dados", expanded=False):
        st.dataframe(df_origem.head(10), width="stretch")
        st.success(f"{len(df_origem)} registros")

    # =========================
    # OPERAÇÃO
    # =========================
    op = st.radio(
        "Operação",
        ["Cadastro", "Estoque"],
        horizontal=True,
    )

    tipo = "cadastro" if op == "Cadastro" else "estoque"
    st.session_state["tipo_operacao_bling"] = tipo

    # =========================
    # MODELO
    # =========================
    if tipo == "cadastro":
        modelo = st.file_uploader(
            "Modelo Cadastro",
            type=["xlsx", "xls", "csv"],
            key="modelo_cadastro",
        )

        if modelo:
            df_modelo = ler_planilha_segura(modelo)
            st.session_state["df_modelo_cadastro"] = df_modelo

    else:
        modelo = st.file_uploader(
            "Modelo Estoque",
            type=["xlsx", "xls", "csv"],
            key="modelo_estoque",
        )

        if modelo:
            df_modelo = ler_planilha_segura(modelo)
            st.session_state["df_modelo_estoque"] = df_modelo

        st.text_input("Nome do depósito", key="deposito_nome_manual")

    # 🔥 AUTO AVANÇO (SEM BOTÃO)
    if (
        _safe_df_dados(df_origem)
        and (
            (tipo == "cadastro" and _safe_df_modelo(st.session_state.get("df_modelo_cadastro")))
            or (tipo == "estoque" and _safe_df_modelo(st.session_state.get("df_modelo_estoque")))
        )
    ):
        st.session_state["df_saida"] = df_origem.copy()
        st.session_state["etapa_origem"] = "mapeamento"
        st.rerun()
