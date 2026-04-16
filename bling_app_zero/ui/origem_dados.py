
from __future__ import annotations

import io
from typing import Optional

import pandas as pd
import streamlit as st

from bling_app_zero.core.fornecedor_search import buscar_produtos_fornecedor
from bling_app_zero.ui.app_helpers import (
    ir_para_etapa,
    log_debug,
    safe_df_dados,
    safe_df_estrutura,
)


FORNECEDORES_PADRAO = {
    "Mega Center Eletrônicos": "https://megacentereletronicos.com.br",
    "Atacadum": "https://atacadum.com.br",
    "Personalizado": "",
}


def _ler_arquivo_upload(upload) -> Optional[pd.DataFrame]:
    if upload is None:
        return None

    nome = str(upload.name).lower()

    try:
        if nome.endswith(".csv"):
            bruto = upload.read()
            for encoding in ("utf-8", "utf-8-sig", "latin1"):
                for sep in (",", ";"):
                    try:
                        return pd.read_csv(io.BytesIO(bruto), encoding=encoding, sep=sep)
                    except Exception:
                        continue
            return None

        if nome.endswith(".xlsx") or nome.endswith(".xls"):
            return pd.read_excel(upload)

    except Exception as exc:
        log_debug(f"Falha ao ler upload: {exc}", "ERROR")
        return None

    return None


def _render_operacao() -> None:
    st.subheader("1) Operação")

    escolha = st.radio(
        "Escolha o tipo de fluxo",
        options=["Cadastro de Produtos", "Atualização de Estoque"],
        index=0 if st.session_state.get("tipo_operacao") == "Cadastro de Produtos" else 1,
        horizontal=True,
    )

    st.session_state["tipo_operacao"] = escolha
    st.session_state["tipo_operacao_bling"] = (
        "cadastro" if escolha == "Cadastro de Produtos" else "estoque"
    )


def _render_origem_planilha() -> None:
    st.subheader("2) Origem por planilha")

    upload = st.file_uploader(
        "Envie a planilha do fornecedor",
        type=["csv", "xlsx", "xls"],
        key="upload_origem_fornecedor",
    )

    if upload is not None:
        df = _ler_arquivo_upload(upload)
        if safe_df_estrutura(df):
            st.session_state["df_origem"] = df.copy()
            log_debug(f"Planilha carregada com {len(df)} linhas.", "INFO")
            st.success("Planilha carregada com sucesso.")
            st.dataframe(df.head(10), use_container_width=True)
        else:
            st.error("Não foi possível ler a planilha enviada.")


def _render_busca_fornecedor() -> None:
    st.subheader("2) Busca no site do fornecedor")

    fornecedor = st.selectbox(
        "Fornecedor",
        options=list(FORNECEDORES_PADRAO.keys()),
        index=0,
    )

    url_padrao = FORNECEDORES_PADRAO.get(fornecedor, "")
    url_atual = st.text_input(
        "URL base do fornecedor",
        value=url_padrao or st.session_state.get("fornecedor_url", ""),
        placeholder="https://fornecedor.com.br",
    )

    termo = st.text_input(
        "O que deseja buscar no site",
        value=st.session_state.get("fornecedor_busca", ""),
        placeholder="Ex.: fone bluetooth, carregador, cabo usb",
    )

    limite = st.number_input(
        "Limite de produtos",
        min_value=1,
        max_value=100,
        value=20,
        step=1,
    )

    st.session_state["fornecedor_nome"] = fornecedor
    st.session_state["fornecedor_url"] = url_atual
    st.session_state["fornecedor_busca"] = termo

    if st.button("Buscar no site do fornecedor", type="primary", use_container_width=True):
        if not url_atual.strip():
            st.warning("Informe a URL base do fornecedor.")
            return
        if not termo.strip():
            st.warning("Informe o termo da busca.")
            return

        with st.spinner("Buscando produtos no site..."):
            df_busca = buscar_produtos_fornecedor(
                base_url=url_atual,
                termo=termo,
                limite=int(limite),
            )

        st.session_state["df_busca_site"] = df_busca

        if safe_df_dados(df_busca):
            st.session_state["df_origem"] = df_busca.copy()
            st.success(f"Busca concluída com {len(df_busca)} resultado(s).")
            st.dataframe(df_busca, use_container_width=True)
        else:
            st.warning(
                "Nenhum produto foi encontrado por busca genérica. "
                "Se esse fornecedor usar site muito dinâmico, o próximo passo é plugar um crawler dedicado."
            )


def _render_modelo_bling() -> None:
    st.subheader("3) Modelo do Bling")

    operacao_bling = st.session_state.get("tipo_operacao_bling", "cadastro")

    if operacao_bling == "cadastro":
        upload_modelo = st.file_uploader(
            "Modelo de cadastro do Bling (opcional)",
            type=["csv", "xlsx", "xls"],
            key="upload_modelo_cadastro",
        )
    else:
        upload_modelo = st.file_uploader(
            "Modelo de estoque do Bling (opcional)",
            type=["csv", "xlsx", "xls"],
            key="upload_modelo_estoque",
        )

    if upload_modelo is not None:
        df_modelo = _ler_arquivo_upload(upload_modelo)
        if safe_df_estrutura(df_modelo):
            st.session_state["df_modelo"] = df_modelo.copy()
            st.session_state["colunas_modelo"] = [str(c) for c in df_modelo.columns.tolist()]
            st.success("Modelo carregado com sucesso.")
            st.dataframe(df_modelo.head(5), use_container_width=True)
        else:
            st.error("Não foi possível ler o modelo enviado.")


def _render_resumo() -> None:
    st.subheader("4) Revisão rápida")

    df_origem = st.session_state.get("df_origem")
    if safe_df_dados(df_origem):
        st.success(
            f"Origem pronta: {len(df_origem)} linha(s) e {len(df_origem.columns)} coluna(s)."
        )
        st.dataframe(df_origem.head(5), use_container_width=True)
    else:
        st.info("Ainda não há dados de origem prontos.")


def render_origem_dados() -> None:
    st.title("Origem dos dados")

    _render_operacao()

    modo_origem = st.radio(
        "Como deseja trazer os dados?",
        options=["Planilha do fornecedor", "Buscar no site do fornecedor"],
        index=0 if st.session_state.get("origem_dados", "planilha") == "planilha" else 1,
        horizontal=True,
    )

    st.session_state["origem_dados"] = (
        "planilha" if modo_origem == "Planilha do fornecedor" else "site"
    )

    if st.session_state["origem_dados"] == "planilha":
        _render_origem_planilha()
    else:
        _render_busca_fornecedor()

    _render_modelo_bling()
    _render_resumo()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Limpar origem", use_container_width=True):
            for chave in ["df_origem", "df_busca_site", "df_modelo", "colunas_modelo"]:
                if chave in st.session_state:
                    del st.session_state[chave]
            st.rerun()

    with col2:
        if st.button(
            "Continuar para precificação",
            type="primary",
            use_container_width=True,
            disabled=not safe_df_dados(st.session_state.get("df_origem")),
        ):
            ir_para_etapa("precificacao")
