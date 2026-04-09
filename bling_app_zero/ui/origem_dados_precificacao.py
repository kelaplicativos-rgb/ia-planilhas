from __future__ import annotations

import hashlib
import pandas as pd
import streamlit as st

from bling_app_zero.core.precificacao import aplicar_precificacao_no_fluxo
from bling_app_zero.ui.app_helpers import log_debug
from bling_app_zero.ui.origem_dados_estado import safe_df_dados


def safe_float(valor, default: float = 0.0) -> float:
    try:
        if valor is None or valor == "":
            return default
        return float(valor)
    except Exception:
        return default


def _normalizar_nome_coluna(nome: str) -> str:
    try:
        return str(nome).strip().lower()
    except Exception:
        return ""


def _detectar_coluna_venda(df: pd.DataFrame) -> str:
    candidatos = [
        "preço unitário",
        "preco unitario",
        "preço de venda",
        "preco de venda",
        "preço venda",
        "preco venda",
        "preço",
        "preco",
        "valor venda",
        "valor",
    ]

    for col in df.columns:
        nome = _normalizar_nome_coluna(col)
        for c in candidatos:
            if c in nome:
                return col

    return df.columns[0]


def _detectar_coluna_resultado_precificacao(
    df: pd.DataFrame,
    coluna_base: str,
    coluna_destino: str,
) -> str:
    candidatos = [
        "preço calculado",
        "preco calculado",
        "preço final",
        "preco final",
        "preço sugerido",
        "preco sugerido",
        "preço venda",
        "preco venda",
        "preço de venda",
        "preco de venda",
        "valor venda",
        "valor final",
        "preço unitário",
        "preco unitario",
    ]

    for col in df.columns:
        nome = _normalizar_nome_coluna(col)
        for c in candidatos:
            if c in nome:
                return col

    if coluna_destino in df.columns and coluna_destino != coluna_base:
        return coluna_destino

    if coluna_base in df.columns:
        return coluna_base

    return df.columns[0]


def coletar_parametros_precificacao() -> dict:
    return {
        "coluna_preco": st.session_state.get("coluna_preco_base"),
        "impostos": safe_float(st.session_state.get("perc_impostos", 0)),
        "lucro": safe_float(st.session_state.get("margem_lucro", 0)),
        "custo_fixo": safe_float(st.session_state.get("custo_fixo", 0)),
        "taxa": safe_float(st.session_state.get("taxa_extra", 0)),
    }


def _garantir_base_precificacao(df_base: pd.DataFrame) -> pd.DataFrame:
    try:
        hash_atual = hashlib.md5(str(df_base.head(20)).encode()).hexdigest()
        hash_salvo = st.session_state.get("_precificacao_df_base_hash", "")

        if (
            "df_base_precificacao" not in st.session_state
            or hash_atual != hash_salvo
        ):
            st.session_state["df_base_precificacao"] = df_base.copy()
            st.session_state["_precificacao_df_base_hash"] = hash_atual

        return st.session_state["df_base_precificacao"].copy()
    except Exception:
        return df_base.copy()


def _aplicar_precificacao(df_base: pd.DataFrame) -> pd.DataFrame | None:
    try:
        params = coletar_parametros_precificacao()

        coluna_preco = str(params.get("coluna_preco") or "").strip()
        if not coluna_preco or coluna_preco not in df_base.columns:
            return None

        df_precificado = aplicar_precificacao_no_fluxo(df_base.copy(), params)

        if not safe_df_dados(df_precificado):
            return None

        coluna_destino = _detectar_coluna_venda(df_precificado)
        coluna_resultado = _detectar_coluna_resultado_precificacao(
            df_precificado,
            coluna_preco,
            coluna_destino,
        )

        # 🔥 GARANTIA: jogar preço calculado na coluna real de venda
        df_precificado[coluna_destino] = df_precificado[coluna_resultado].copy()

        st.session_state["coluna_preco_unitario_destino"] = coluna_destino
        st.session_state["preco_calculado_coluna"] = coluna_resultado

        return df_precificado

    except Exception as e:
        log_debug(f"Erro na precificação: {e}", "ERRO")
        return None


def render_precificacao(df_base):
    if not safe_df_dados(df_base):
        return

    df_base_calculo = _garantir_base_precificacao(df_base)
    colunas = list(df_base_calculo.columns)

    if not colunas:
        return

    st.selectbox(
        "Coluna de custo",
        options=colunas,
        key="coluna_preco_base",
    )

    col1, col2 = st.columns(2)

    with col1:
        st.number_input("Margem (%)", min_value=0.0, key="margem_lucro")
        st.number_input("Impostos (%)", min_value=0.0, key="perc_impostos")

    with col2:
        st.number_input("Custo fixo", min_value=0.0, key="custo_fixo")
        st.number_input("Taxa (%)", min_value=0.0, key="taxa_extra")

    df_precificado = _aplicar_precificacao(df_base_calculo)

    if safe_df_dados(df_precificado):
        # 🔥 CORREÇÃO PRINCIPAL
        st.session_state["df_base"] = df_precificado.copy()
        st.session_state["df_dados"] = df_precificado.copy()
        st.session_state["df_saida"] = df_precificado.copy()
        st.session_state["df_final"] = df_precificado.copy()

        df_preview = df_precificado
    else:
        df_preview = df_base_calculo

    with st.expander("📊 Preview da precificação", expanded=True):
        st.dataframe(df_preview.head(10), use_container_width=True, hide_index=True)
