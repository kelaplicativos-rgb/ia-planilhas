
from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import (
    formatar_numero_bling,
    log_debug,
    normalizar_coluna_busca,
    safe_df_dados,
    sincronizar_etapa_global,
    to_float_brasil,
)


# ============================================================
# HELPERS
# ============================================================

def _get_df_base() -> pd.DataFrame | None:
    for chave in [
        "df_saida",
        "df_final",
        "df_precificado",
        "df_calc_precificado",
        "df_origem",
    ]:
        df = st.session_state.get(chave)
        if safe_df_dados(df):
            return df.copy()
    return None


def _coluna_operacional_preferida(df: pd.DataFrame) -> str:
    candidatos_preferidos = [
        "preco base",
        "preco_base",
        "preco",
        "preco site",
        "preco_site",
        "valor",
        "valor unitario",
        "valor_unitario",
        "preço base",
        "preço",
        "preço site",
        "preço unitário",
    ]

    mapa = {normalizar_coluna_busca(col): col for col in df.columns}
    for candidato in candidatos_preferidos:
        chave = normalizar_coluna_busca(candidato)
        if chave in mapa:
            return mapa[chave]

    for col in df.columns:
        ncol = normalizar_coluna_busca(col)
        if any(c in ncol for c in ["preco", "valor"]):
            return col

    return ""


def _get_colunas_numericas(df: pd.DataFrame) -> list[str]:
    colunas_validas: list[str] = []
    for col in df.columns:
        serie = df[col].apply(to_float_brasil)
        if pd.Series(serie).fillna(0).sum() >= 0 and pd.Series(serie).notna().sum() > 0:
            if any(v != 0 for v in serie) or len(df) > 0:
                colunas_validas.append(col)
    return colunas_validas


def _calcular_preco(
    df: pd.DataFrame,
    coluna_base: str,
    margem: float,
    impostos: float,
    custo_fixo: float,
    taxa_extra: float,
) -> pd.DataFrame:
    df_calc = df.copy()

    base = df_calc[coluna_base].apply(to_float_brasil).fillna(0.0)
    fator = 1 + (float(margem) / 100.0) + (float(impostos) / 100.0)
    preco = (base * fator) + float(custo_fixo) + float(taxa_extra)

    df_calc["Preço calculado"] = preco.round(2)
    return df_calc


def _aplicar_preco_no_modelo(df: pd.DataFrame, tipo_operacao_bling: str) -> pd.DataFrame:
    df_out = df.copy()
    tipo = str(tipo_operacao_bling).strip().lower()

    if "Preço calculado" not in df_out.columns:
        return df_out

    if tipo == "estoque":
        destino_preferido = "Preço unitário (OBRIGATÓRIO)"
        if destino_preferido not in df_out.columns:
            df_out[destino_preferido] = ""
        df_out[destino_preferido] = df_out["Preço calculado"].apply(formatar_numero_bling)
    else:
        destino_preferido = "Preço de venda"
        if destino_preferido not in df_out.columns:
            df_out[destino_preferido] = ""
        df_out[destino_preferido] = df_out["Preço calculado"].apply(formatar_numero_bling)

    return df_out


def _manter_preco_original(df: pd.DataFrame, coluna_base: str, tipo_operacao_bling: str) -> pd.DataFrame:
    df_out = df.copy()
    tipo = str(tipo_operacao_bling).strip().lower()

    df_out["Preço calculado"] = df_out[coluna_base].apply(to_float_brasil)

    if tipo == "estoque":
        destino = "Preço unitário (OBRIGATÓRIO)"
    else:
        destino = "Preço de venda"

    if destino not in df_out.columns:
        df_out[destino] = ""

    df_out[destino] = df_out["Preço calculado"].apply(formatar_numero_bling)
    return df_out


# ============================================================
# RENDER
# ============================================================

def render_origem_precificacao() -> None:
    st.markdown("### Precificação")
    st.caption(
        "Defina se quer usar a calculadora ou manter o preço original da origem."
    )

    df_base = _get_df_base()
    if not safe_df_dados(df_base):
        st.warning("Nenhum dado disponível para precificação.")
        if st.button("⬅️ Voltar para origem", use_container_width=True):
            sincronizar_etapa_global("origem")
            st.rerun()
        return

    tipo_operacao_bling = st.session_state.get("tipo_operacao_bling", "cadastro")

    colunas_numericas = _get_colunas_numericas(df_base)
    if not colunas_numericas:
        st.warning("Nenhuma coluna numérica encontrada para cálculo.")
        if st.button("⬅️ Voltar para origem", use_container_width=True):
            sincronizar_etapa_global("origem")
            st.rerun()
        return

    preferida = _coluna_operacional_preferida(df_base)
    if preferida and preferida in colunas_numericas:
        default_idx = colunas_numericas.index(preferida)
    else:
        default_idx = 0

    usar_calculadora = st.toggle(
        "Usar calculadora de precificação",
        value=bool(st.session_state.get("usar_calculadora_precificacao", True)),
        key="usar_calculadora_precificacao",
    )

    st.markdown("#### Base de cálculo")
    coluna_base = st.selectbox(
        "Selecione a coluna de preço base",
        options=colunas_numericas,
        index=default_idx,
        key="precificacao_coluna_base",
    )

    if not usar_calculadora:
        st.info("O sistema vai manter o preço da planilha fornecedora/site.")

        df_final = _manter_preco_original(df_base, coluna_base, tipo_operacao_bling)
        st.session_state["df_calc_precificado"] = df_final.copy()
        st.session_state["df_precificado"] = df_final.copy()
        st.session_state["df_saida"] = df_final.copy()

        with st.expander("Preview da precificação", expanded=False):
            st.dataframe(df_final.head(50), use_container_width=True)

        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬅️ Voltar", use_container_width=True, key="voltar_precificacao_sem_calc"):
                sincronizar_etapa_global("origem")
                st.rerun()
        with col2:
            if st.button("Continuar ➜", use_container_width=True, key="continuar_precificacao_sem_calc"):
                log_debug("Precificação mantida com preço original", "INFO")
                sincronizar_etapa_global("mapeamento")
                st.rerun()
        return

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
    df_final = _aplicar_preco_no_modelo(df_calc, tipo_operacao_bling)

    st.session_state["df_calc_precificado"] = df_calc.copy()
    st.session_state["df_precificado"] = df_final.copy()
    st.session_state["df_saida"] = df_final.copy()

    with st.expander("Preview da precificação", expanded=False):
        st.dataframe(df_final.head(50), use_container_width=True)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Voltar", use_container_width=True, key="voltar_precificacao"):
            sincronizar_etapa_global("origem")
            st.rerun()

    with col2:
        pode_avancar = safe_df_dados(df_final)
        if st.button("Continuar ➜", use_container_width=True, disabled=not pode_avancar, key="continuar_precificacao"):
            log_debug("Precificação aplicada com sucesso", "INFO")
            sincronizar_etapa_global("mapeamento")
            st.rerun()
