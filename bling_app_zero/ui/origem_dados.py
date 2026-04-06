from __future__ import annotations

import json
import streamlit as st

from bling_app_zero.ui.origem_dados_helpers import (
    log_debug,
    ler_planilha_segura,
)
from bling_app_zero.ui.origem_dados_site import render_origem_site
from bling_app_zero.core.precificacao import aplicar_precificacao_automatica


def _safe_df_dados(df):
    try:
        if df is None:
            return False
        if not hasattr(df, "columns"):
            return False
        if len(df.columns) == 0:
            return False
        if df.empty:
            return False
        return True
    except Exception:
        return False


def _safe_df_modelo(df):
    try:
        if df is None:
            return False
        if not hasattr(df, "columns"):
            return False
        if len(df.columns) == 0:
            return False
        return True
    except Exception:
        return False


def _detectar_coluna_deposito(df):
    for col in df.columns:
        nome = str(col).lower().strip()
        if "deposit" in nome or "depós" in nome or "deposito" in nome:
            return col
    return None


def _aplicar_deposito(df, deposito):
    if not deposito:
        return df

    df_saida = df.copy()
    col_dep = _detectar_coluna_deposito(df_saida)

    if col_dep:
        df_saida[col_dep] = deposito
    else:
        df_saida["Depósito"] = deposito

    return df_saida


def _normalizar_coluna_numerica(df, coluna):
    if coluna not in df.columns:
        return df

    df_saida = df.copy()

    try:
        serie = df_saida[coluna].astype(str).str.strip()
        serie = serie.str.replace("R$", "", regex=False)
        serie = serie.str.replace(".", "", regex=False)
        serie = serie.str.replace(",", ".", regex=False)

        df_saida[coluna] = serie.astype(float)
    except Exception:
        pass

    return df_saida


def _coletar_parametros_precificacao():
    return {
        "percentual_impostos": float(st.session_state.get("perc_impostos", 0) or 0),
        "margem_lucro": float(st.session_state.get("margem_lucro", 0) or 0),
        "custo_fixo": float(st.session_state.get("custo_fixo", 0) or 0),
        "taxa_extra": float(st.session_state.get("taxa_extra", 0) or 0),
    }


def _aplicar_precificacao_com_fallback(df_base, coluna_preco):
    df_temp = _normalizar_coluna_numerica(df_base, coluna_preco)

    kwargs = _coletar_parametros_precificacao()

    try:
        return aplicar_precificacao_automatica(
            df_temp,
            coluna_preco=coluna_preco,
            **kwargs,
        )
    except TypeError:
        return aplicar_precificacao_automatica(df_temp, **kwargs)


def _render_precificacao(df_base):
    st.markdown("### Precificação")

    if not _safe_df_dados(df_base):
        return

    colunas = list(df_base.columns)

    coluna_preco = st.selectbox(
        "Selecione a coluna de PREÇO DE CUSTO",
        options=colunas,
        key="coluna_preco_base",
    )

    col1, col2 = st.columns(2)

    with col1:
        st.number_input("Margem (%)", min_value=0.0, key="margem_lucro")
        st.number_input("Impostos (%)", min_value=0.0, key="perc_impostos")

    with col2:
        st.number_input("Custo fixo", min_value=0.0, key="custo_fixo")
        st.number_input("Taxa extra (%)", min_value=0.0, key="taxa_extra")

    try:
        df_precificado = _aplicar_precificacao_com_fallback(df_base, coluna_preco)

        if _safe_df_dados(df_precificado):
            st.session_state["df_precificado"] = df_precificado.copy()
            st.session_state["df_saida"] = df_precificado.copy()

            with st.expander("👁️ Prévia da precificação", expanded=False):
                st.dataframe(df_precificado.head(10), width="stretch")

    except Exception as e:
        log_debug(f"Erro na precificação: {e}")


def render_origem_dados() -> None:
    etapa_atual = st.session_state.get("etapa_origem")

    if etapa_atual in ["mapeamento", "final"]:
        return

    st.subheader("Origem dos dados")

    # 🔥 NOVO — TIPO DE OPERAÇÃO
    operacao = st.radio(
        "Selecione a operação",
        ["Cadastro de Produtos", "Atualização de Estoque"],
        key="tipo_operacao",
    )

    # 🔥 NOVO — MODELOS
    st.markdown("### Modelos Bling")

    modelo_cadastro = None
    modelo_estoque = None

    if operacao == "Cadastro de Produtos":
        modelo_cadastro = st.file_uploader(
            "Anexar modelo de cadastro",
            type=["xlsx", "xls"],
            key="modelo_cadastro",
        )

    else:
        modelo_estoque = st.file_uploader(
            "Anexar modelo de estoque",
            type=["xlsx", "xls"],
            key="modelo_estoque",
        )

    # =========================
    # ORIGEM
    # =========================
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
        )

        if arquivo:
            df_origem = ler_planilha_segura(arquivo)

    elif origem == "Site":
        df_origem = render_origem_site()

    elif origem == "XML":
        st.info("XML em construção")
        return

    if not _safe_df_dados(df_origem):
        return

    st.session_state["df_origem"] = df_origem

    # 🔥 NOVO — PREVIEW FORNECEDOR
    with st.expander("📄 Prévia da planilha do fornecedor", expanded=False):
        st.dataframe(df_origem.head(10), width="stretch")

    # =========================
    # PRECIFICAÇÃO
    # =========================
    _render_precificacao(df_origem)

    df_saida = st.session_state.get("df_saida")

    if _safe_df_dados(df_saida):

        # 🔥 BOTÃO PARA AVANÇAR (SEM AUTO FLUXO)
        if st.button("➡️ Continuar para mapeamento", use_container_width=True):
            st.session_state["df_final"] = df_saida.copy()
            st.session_state["etapa_origem"] = "mapeamento"
            st.rerun()
