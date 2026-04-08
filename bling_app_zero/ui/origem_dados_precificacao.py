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


def _df_preview_seguro(df: pd.DataFrame | None):
    try:
        if not safe_df_dados(df):
            return df

        df_preview = df.copy()

        for col in df_preview.columns:
            try:
                df_preview[col] = df_preview[col].apply(
                    lambda x: "" if pd.isna(x) else str(x)
                )
            except Exception:
                pass

        return df_preview.replace(
            {"nan": "", "None": "", "<NA>": "", "NaT": ""}
        )
    except Exception:
        return df


def coletar_parametros_precificacao():
    return {
        "coluna_preco": st.session_state.get("coluna_preco_base"),
        "impostos": safe_float(st.session_state.get("perc_impostos", 0)),
        "lucro": safe_float(st.session_state.get("margem_lucro", 0)),
        "custo_fixo": safe_float(st.session_state.get("custo_fixo", 0)),
        "taxa": safe_float(st.session_state.get("taxa_extra", 0)),
    }


def _hash_parametros(params: dict) -> str:
    return hashlib.md5(str(params).encode()).hexdigest()


def _sincronizar_df(df):
    try:
        st.session_state["df_precificado"] = df.copy()
        st.session_state["df_dados"] = df.copy()
        st.session_state["df_saida"] = df.copy()
        st.session_state["df_final"] = df.copy()

        st.session_state["df_origem"] = df.copy()

        st.session_state["bloquear_campos_auto"] = {
            "preco": True,
            "preço": True,
            "preco de venda": True,
            "preço de venda": True,
        }

    except Exception as e:
        log_debug(f"Erro sincronizar DF: {e}", "ERRO")


def _aplicar_precificacao(df_base):
    try:
        params = coletar_parametros_precificacao()

        if not params.get("coluna_preco"):
            return

        df_precificado = aplicar_precificacao_no_fluxo(df_base.copy(), params)

        if safe_df_dados(df_precificado):
            _sincronizar_df(df_precificado)

    except Exception as e:
        log_debug(f"Erro precificação: {e}", "ERRO")


def render_precificacao(df_base):

    st.markdown("### 💰 Precificação")

    if not safe_df_dados(df_base):
        return

    colunas = list(df_base.columns)

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

    # =========================================================
    # 🔥 CONTROLE INTELIGENTE (SEM LOOP)
    # =========================================================
    params = coletar_parametros_precificacao()
    hash_atual = _hash_parametros(params)

    if st.session_state.get("hash_precificacao") != hash_atual:
        st.session_state["hash_precificacao"] = hash_atual
        _aplicar_precificacao(df_base)

    # =========================================================
    # PREVIEW
    # =========================================================
    df = st.session_state.get("df_precificado")

    if safe_df_dados(df):
        with st.expander("📊 Preview da precificação", expanded=True):
            st.dataframe(
                _df_preview_seguro(df).head(10),
                use_container_width=True,
            )
