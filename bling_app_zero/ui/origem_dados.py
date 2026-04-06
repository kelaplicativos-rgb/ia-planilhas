from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.origem_dados_helpers import (
    log_debug,
    ler_planilha_segura,
)
from bling_app_zero.ui.origem_dados_site import render_origem_site


def _safe_df(df):
    try:
        if df is None or df.empty:
            return None
        return df
    except Exception:
        return None


def _limpar_modelos_estado() -> None:
    for chave in [
        "df_modelo_cadastro",
        "df_modelo_estoque",
        "modelo_cadastro_nome",
        "modelo_estoque_nome",
    ]:
        if chave in st.session_state:
            del st.session_state[chave]


def render_origem_dados() -> None:
    # não renderiza a origem quando já estiver na etapa seguinte
    if st.session_state.get("etapa_origem") == "mapeamento":
        return

    st.subheader("Origem dos dados")

    origem = st.selectbox(
        "Selecione a origem",
        ["Planilha", "XML", "Site"],
        key="origem_tipo",
    )

    df_origem = None

    # =========================
    # PLANILHA
    # =========================
    if origem == "Planilha":
        arquivo = st.file_uploader(
            "Envie a planilha",
            type=["xlsx", "xls", "csv", "xlsm", "xlsb"],
            key="upload_planilha_origem",
        )

        if arquivo:
            df_origem = ler_planilha_segura(arquivo)

            if _safe_df(df_origem) is None:
                st.error("Erro ao ler planilha")
                return

    # =========================
    # XML
    # =========================
    elif origem == "XML":
        st.warning("XML ainda em construção")
        return

    # =========================
    # SITE
    # =========================
    elif origem == "Site":
        try:
            df_origem = render_origem_site()
        except Exception as e:
            log_debug(f"Erro ao buscar dados do site: {e}", "ERROR")
            st.error("Erro ao buscar dados do site")
            return

    if _safe_df(df_origem) is None:
        return

    st.session_state["df_origem"] = df_origem

    # ==========================================================
    # PREVIEW
    # ==========================================================
    st.divider()
    st.subheader("Pré-visualização dos dados")

    st.dataframe(df_origem.head(10), width="stretch")
    st.success(f"{len(df_origem)} registros carregados")

    # ==========================================================
    # OPERAÇÃO
    # ==========================================================
    st.divider()
    st.subheader("Selecione a operação")

    valor_atual = st.session_state.get("tipo_operacao_bling", "cadastro")

    opcoes = {
        "Cadastro / atualização de produtos": "cadastro",
        "Atualização de estoque": "estoque",
    }

    labels = list(opcoes.keys())
    indice = 0 if valor_atual != "estoque" else 1

    escolha_label = st.radio(
        "O que será feito?",
        options=labels,
        index=indice,
        key="radio_operacao_bling",
    )

    escolha_valor = opcoes[escolha_label]
    st.session_state["tipo_operacao_bling"] = escolha_valor

    if escolha_valor == "cadastro":
        st.info("Modo: Cadastro de produtos")
    else:
        st.info("Modo: Atualização de estoque")

    # ==========================================================
    # MODELO PARA DOWNLOAD
    # ==========================================================
    st.divider()
    st.subheader("Planilha modelo para o download")

    if escolha_valor == "cadastro":
        modelo_cadastro = st.file_uploader(
            "Anexe o modelo oficial de Cadastro",
            type=["xlsx", "xls", "xlsm", "xlsb", "csv"],
            key="upload_modelo_cadastro",
        )

        if modelo_cadastro is not None:
            df_modelo_cadastro = ler_planilha_segura(modelo_cadastro)
            if _safe_df(df_modelo_cadastro) is None:
                st.error("Erro ao ler o modelo de cadastro")
                return

            st.session_state["df_modelo_cadastro"] = df_modelo_cadastro
            st.session_state["modelo_cadastro_nome"] = modelo_cadastro.name
            st.success(f"Modelo de cadastro carregado: {modelo_cadastro.name}")

    else:
        modelo_estoque = st.file_uploader(
            "Anexe o modelo oficial de Estoque",
            type=["xlsx", "xls", "xlsm", "xlsb", "csv"],
            key="upload_modelo_estoque",
        )

        if modelo_estoque is not None:
            df_modelo_estoque = ler_planilha_segura(modelo_estoque)
            if _safe_df(df_modelo_estoque) is None:
                st.error("Erro ao ler o modelo de estoque")
                return

            st.session_state["df_modelo_estoque"] = df_modelo_estoque
            st.session_state["modelo_estoque_nome"] = modelo_estoque.name
            st.success(f"Modelo de estoque carregado: {modelo_estoque.name}")

        st.text_input(
            "Nome do depósito",
            key="deposito_nome_manual",
            help="Esse valor será usado para preencher a coluna de depósito no modelo de estoque.",
        )

    # ==========================================================
    # BOTÃO CONTINUAR
    # ==========================================================
    st.divider()

    if st.button("➡️ Continuar para mapeamento", width="stretch"):
        try:
            st.session_state["df_saida"] = df_origem.copy()
            st.session_state["etapa_origem"] = "mapeamento"
            st.rerun()
        except Exception as e:
            log_debug(f"Erro ao ir para mapeamento: {e}", "ERROR")
            st.error("Erro ao avançar")
