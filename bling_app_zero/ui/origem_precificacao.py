
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    log_debug,
    safe_df_dados,
    sincronizar_etapa_global,
)


def _get_df_base() -> pd.DataFrame | None:
    for chave in ["df_saida", "df_final", "df_origem"]:
        df = st.session_state.get(chave)
        if safe_df_dados(df):
            return df.copy()
    return None


def _get_colunas_numericas(df: pd.DataFrame) -> list[str]:
    try:
        colunas_validas = []
        for col in df.columns:
            serie = pd.to_numeric(df[col], errors="coerce")
            if serie.notna().sum() > 0:
                colunas_validas.append(col)
        return colunas_validas
    except Exception:
        return []


def _calcular_preco(
    df: pd.DataFrame,
    coluna_base: str,
    margem: float,
    impostos: float,
    custo_fixo: float,
    taxa_extra: float,
) -> pd.DataFrame:
    try:
        df_calc = df.copy()
        base = pd.to_numeric(df_calc[coluna_base], errors="coerce").fillna(0)
        fator = 1 + (margem / 100) + (impostos / 100)
        preco = (base * fator) + custo_fixo + taxa_extra
        df_calc["Preço calculado"] = preco.round(2)
        return df_calc
    except Exception as e:
        log_debug(f"Erro cálculo preço: {e}", "ERROR")
        return df.copy()


def _aplicar_preco_no_modelo(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df_out = df.copy()
        col_preco = None

        for col in df_out.columns:
            nome = str(col).lower()
            if "preço de venda" in nome or "preco de venda" in nome:
                col_preco = col
                break
            if "preço unitário" in nome or "preco unitario" in nome:
                col_preco = col
                break

        if col_preco:
            df_out[col_preco] = df_out["Preço calculado"]
        else:
            df_out["Preço de venda"] = df_out["Preço calculado"]

        return df_out
    except Exception as e:
        log_debug(f"Erro aplicar preço modelo: {e}", "ERROR")
        return df.copy()


def render_origem_precificacao() -> None:
    st.markdown("### 💰 Precificação")

    df_base = _get_df_base()

    if not safe_df_dados(df_base):
        st.warning("Nenhum dado disponível para precificação.")
        if st.button("⬅️ Voltar para origem", use_container_width=True):
            sincronizar_etapa_global("origem")
            st.rerun()
        return

    colunas_numericas = _get_colunas_numericas(df_base)

    if not colunas_numericas:
        st.warning("Nenhuma coluna numérica encontrada para cálculo.")
        if st.button("⬅️ Voltar para origem", use_container_width=True):
            sincronizar_etapa_global("origem")
            st.rerun()
        return

    st.markdown("#### Base de cálculo")

    coluna_base = st.selectbox(
        "Selecione a coluna de preço base",
        options=colunas_numericas,
        key="precificacao_coluna_base",
    )

    col1, col2 = st.columns(2)

    with col1:
        margem = st.number_input(
            "Margem (%)",
            min_value=0.0,
            value=float(st.session_state.get("precificacao_margem", 30.0)),
            step=1.0,
            key="precificacao_margem",
        )

        impostos = st.number_input(
            "Impostos (%)",
            min_value=0.0,
            value=float(st.session_state.get("precificacao_impostos", 10.0)),
            step=1.0,
            key="precificacao_impostos",
        )

    with col2:
        custo_fixo = st.number_input(
            "Custo fixo (R$)",
            min_value=0.0,
            value=float(st.session_state.get("precificacao_custo_fixo", 0.0)),
            step=1.0,
            key="precificacao_custo_fixo",
        )

        taxa_extra = st.number_input(
            "Taxa extra (R$)",
            min_value=0.0,
            value=float(st.session_state.get("precificacao_taxa_extra", 0.0)),
            step=1.0,
            key="precificacao_taxa_extra",
        )

    df_calc = _calcular_preco(
        df_base,
        coluna_base,
        margem,
        impostos,
        custo_fixo,
        taxa_extra,
    )

    df_final = _aplicar_preco_no_modelo(df_calc)

    st.session_state["df_calc_precificado"] = df_calc.copy()
    st.session_state["df_precificado"] = df_final.copy()
    st.session_state["df_saida"] = df_final.copy()

    with st.expander("🔎 Preview da precificação", expanded=False):
        st.dataframe(df_final.head(20), use_container_width=True)

    st.markdown("---")

    col1, col2 = st.columns(2)

    with col1:
        if st.button("⬅️ Voltar", use_container_width=True):
            sincronizar_etapa_global("origem")
            st.rerun()

    with col2:
        pode_avancar = safe_df_dados(df_final)
        if st.button("Continuar ➜", use_container_width=True, disabled=not pode_avancar):
            sincronizar_etapa_global("mapeamento")
            st.rerun()

    log_debug("Precificação aplicada com sucesso", "INFO")
