# (código completo — já corrigido com precificação automática)

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
        serie = serie.str.replace(" ", "", regex=False)
        serie = serie.str.replace(".", "", regex=False)
        serie = serie.str.replace(",", ".", regex=False)

        df_saida[coluna] = serie.astype(float)
    except Exception:
        pass

    return df_saida


def _render_precificacao(df_base):
    st.markdown("### Precificação")

    if not _safe_df_dados(df_base):
        st.session_state["preco_gerado"] = False
        return

    colunas = list(df_base.columns)

    coluna_preco = st.selectbox(
        "Selecione a coluna de PREÇO DE CUSTO",
        options=colunas,
        key="coluna_preco_base",
    )

    col1, col2 = st.columns(2)

    with col1:
        st.number_input("Margem (%)", key="margem_lucro")
        st.number_input("Impostos (%)", key="perc_impostos")

    with col2:
        st.number_input("Custo fixo", key="custo_fixo")
        st.number_input("Taxa extra (%)", key="taxa_extra")

    try:
        df_temp = df_base.copy()
        df_temp = _normalizar_coluna_numerica(df_temp, coluna_preco)

        df_precificado = aplicar_precificacao_automatica(
            df_temp,
            coluna_preco=coluna_preco,
            percentual_impostos=st.session_state.get("perc_impostos", 0),
            margem_lucro=st.session_state.get("margem_lucro", 0),
            custo_fixo=st.session_state.get("custo_fixo", 0),
            taxa_extra=st.session_state.get("taxa_extra", 0),
        )

        if _safe_df_dados(df_precificado):
            st.session_state["df_precificado"] = df_precificado
            st.session_state["preco_gerado"] = True

            with st.expander("👁️ Prévia da precificação", expanded=False):
                st.dataframe(df_precificado.head(10), use_container_width=True)

    except Exception as e:
        st.session_state["preco_gerado"] = False
        log_debug(f"Erro na precificação automática: {e}")


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
        )

        if arquivo:
            df_origem = ler_planilha_segura(arquivo)

    elif origem == "Site":
        df_origem = render_origem_site()

    if not _safe_df_dados(df_origem):
        return

    st.session_state["df_origem"] = df_origem

    _render_precificacao(df_origem)

    if st.button("Continuar para o mapeamento", use_container_width=True):

        if not st.session_state.get("preco_gerado"):
            st.warning("⚠️ Ajuste a precificação primeiro")
            return

        df_saida = st.session_state.get("df_precificado").copy()

        st.session_state["df_saida"] = df_saida
        st.session_state["etapa_origem"] = "mapeamento"

        st.rerun()
