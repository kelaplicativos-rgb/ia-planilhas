import streamlit as st
import pandas as pd
from bling_app_zero.ui.app_helpers import safe_df


def _ler_planilha(upload):
    if upload.name.endswith(".csv"):
        return pd.read_csv(upload, dtype=str).fillna("")
    else:
        return pd.read_excel(upload, dtype=str).fillna("")


def render_origem_dados():
    st.subheader("1. Origem dos dados")

    # =========================
    # OPERAÇÃO
    # =========================
    st.markdown("### O que você quer fazer?")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Cadastro de Produtos", use_container_width=True):
            st.session_state["tipo_operacao"] = "cadastro"
            st.session_state["tipo_operacao_bling"] = "cadastro"

    with col2:
        if st.button("Atualização de Estoque", use_container_width=True):
            st.session_state["tipo_operacao"] = "estoque"
            st.session_state["tipo_operacao_bling"] = "estoque"

    if not st.session_state["tipo_operacao"]:
        st.info("Escolha uma operação para continuar")
        return

    st.success(f"Operação: {st.session_state['tipo_operacao']}")

    # =========================
    # DEPÓSITO (SÓ ESTOQUE)
    # =========================
    if st.session_state["tipo_operacao"] == "estoque":
        deposito = st.text_input(
            "Nome do depósito",
            value=st.session_state.get("deposito_nome", "")
        )
        st.session_state["deposito_nome"] = deposito

    # =========================
    # UPLOAD FORNECEDOR
    # =========================
    st.markdown("### Planilha do fornecedor")

    upload_origem = st.file_uploader(
        "Envie a planilha do fornecedor",
        type=["xlsx", "xls", "csv"],
        key="upload_origem"
    )

    if upload_origem:
        df_origem = _ler_planilha(upload_origem)
        st.session_state["df_origem"] = df_origem

        st.success("Planilha do fornecedor carregada")
        st.dataframe(df_origem.head())

    # =========================
    # UPLOAD MODELO
    # =========================
    st.markdown("### Planilha modelo (Bling)")

    upload_modelo = st.file_uploader(
        "Envie a planilha modelo do Bling",
        type=["xlsx", "xls", "csv"],
        key="upload_modelo"
    )

    if upload_modelo:
        df_modelo = _ler_planilha(upload_modelo)
        st.session_state["df_modelo"] = df_modelo

        st.success("Modelo carregado")
        st.dataframe(df_modelo.head())

    # =========================
    # CONTINUAR
    # =========================
    if safe_df(st.session_state.get("df_origem")) and safe_df(st.session_state.get("df_modelo")):
        if st.button("Continuar ➜", use_container_width=True):
            st.session_state["etapa"] = "precificacao"
            st.rerun()
