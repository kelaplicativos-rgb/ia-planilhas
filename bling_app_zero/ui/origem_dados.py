from __future__ import annotations

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


# 🔥 DETECTA COLUNA DEPÓSITO
def _detectar_coluna_deposito(df):
    for col in df.columns:
        nome = str(col).lower()
        if "deposit" in nome or "depós" in nome:
            return col
    return None


# 🔥 APLICA DEPÓSITO
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

    # =========================
    # ORIGEM
    # =========================
    if origem == "Planilha":
        arquivo = st.file_uploader(
            "Envie a planilha",
            type=["xlsx", "xls", "csv", "xlsm", "xlsb"],
            key="upload_planilha_origem",
        )

        if arquivo:
            df_origem = ler_planilha_segura(arquivo)

            if not _safe_df_dados(df_origem):
                st.error("Erro ao ler planilha")
                return

    elif origem == "Site":
        df_origem = render_origem_site()

    if not _safe_df_dados(df_origem):
        return

    st.session_state["df_origem"] = df_origem

    # 🔥 PREVIEW COLAPSADO
    with st.expander("👁️ Pré-visualização dos dados", expanded=False):
        st.dataframe(df_origem.head(10), width="stretch")

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
    deposito = ""

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

        deposito = st.text_input("Nome do depósito", key="deposito_nome_manual")

        # 🔥 GUARDA NO STATE (CORREÇÃO PRINCIPAL)
        if deposito:
            st.session_state["deposito_nome"] = deposito

    # =========================
    # VALIDAÇÃO
    # =========================
    modelo_ok = (
        _safe_df_modelo(st.session_state.get("df_modelo_cadastro"))
        if tipo == "cadastro"
        else _safe_df_modelo(st.session_state.get("df_modelo_estoque"))
    )

    if tipo == "estoque" and modelo_ok and not st.session_state.get("deposito_nome"):
        st.warning("Informe o nome do depósito")
        return

    # =========================
    # 🔥 AUTO FLUXO CORRIGIDO
    # =========================
    if _safe_df_dados(df_origem) and modelo_ok:

        df_saida = df_origem.copy()

        # 🔥 SEMPRE PUXA DO STATE
        deposito_final = st.session_state.get("deposito_nome")

        if tipo == "estoque":
            df_saida = _aplicar_deposito(df_saida, deposito_final)

        # 🔥 APLICA PRECIFICAÇÃO
        df_saida = aplicar_precificacao_automatica(
            df_saida,
            percentual_impostos=st.session_state.get("perc_impostos", 0),
            margem_lucro=st.session_state.get("margem_lucro", 0),
            custo_fixo=st.session_state.get("custo_fixo", 0),
            taxa_extra=st.session_state.get("taxa_extra", 0),
        )

        if df_saida is None or df_saida.empty:
            st.error("Erro nos dados. Não é possível continuar.")
            return

        # 🔥 GARANTE QUE NÃO PERCA NO FLUXO
        st.session_state["df_saida"] = df_saida

        st.session_state["etapa_origem"] = "mapeamento"

        log_debug("Fluxo OK → indo para mapeamento com depósito aplicado")

        st.rerun()
