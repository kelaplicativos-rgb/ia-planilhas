from __future__ import annotations

import hashlib
import pandas as pd
import streamlit as st

from bling_app_zero.core.precificacao import aplicar_precificacao_no_fluxo
from bling_app_zero.ui.app_helpers import log_debug
from bling_app_zero.ui.origem_dados_estado import safe_df_dados


# ==========================================================
# HELPERS
# ==========================================================
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


# ==========================================================
# DETECÇÃO DE COLUNA DESTINO
# ==========================================================
def _detectar_coluna_venda(df: pd.DataFrame) -> str | None:
    prioridades = [
        "preço de venda",
        "preco de venda",
        "valor venda",
    ]

    # prioridade exata
    for p in prioridades:
        for col in df.columns:
            if _normalizar_nome_coluna(col) == p:
                return col

    # fallback
    for col in df.columns:
        nome = _normalizar_nome_coluna(col)
        if "venda" in nome or "preço" in nome:
            return col

    return None


# ==========================================================
# PARAMETROS
# ==========================================================
def coletar_parametros_precificacao() -> dict:
    return {
        "coluna_preco": st.session_state.get("coluna_preco_base"),
        "impostos": safe_float(st.session_state.get("perc_impostos", 0)),
        "lucro": safe_float(st.session_state.get("margem_lucro", 0)),
        "custo_fixo": safe_float(st.session_state.get("custo_fixo", 0)),
        "taxa": safe_float(st.session_state.get("taxa_extra", 0)),
    }


# ==========================================================
# CACHE BASE
# ==========================================================
def _garantir_base_precificacao(df_base: pd.DataFrame) -> pd.DataFrame:
    try:
        hash_atual = hashlib.md5(str(df_base).encode()).hexdigest()
        hash_salvo = st.session_state.get("_precificacao_df_base_hash", "")

        if hash_atual != hash_salvo:
            st.session_state["df_base_precificacao"] = df_base.copy()
            st.session_state["_precificacao_df_base_hash"] = hash_atual

        return st.session_state.get("df_base_precificacao", df_base).copy()
    except Exception:
        return df_base.copy()


# ==========================================================
# APLICAÇÃO CORRIGIDA
# ==========================================================
def _aplicar_precificacao(df_base: pd.DataFrame) -> pd.DataFrame | None:
    try:
        params = coletar_parametros_precificacao()

        coluna_preco = str(params.get("coluna_preco") or "").strip()

        if not coluna_preco or coluna_preco not in df_base.columns:
            return None

        # 🔥 aplica direto
        df_calc = aplicar_precificacao_no_fluxo(df_base.copy(), params)

        if not safe_df_dados(df_calc):
            return None

        # 🔥 coluna destino REAL
        col_venda = _detectar_coluna_venda(df_base)

        if not col_venda:
            return None

        # 🔥 aplica valor calculado diretamente
        df_base[col_venda] = df_calc[col_venda]

        st.session_state["coluna_preco_unitario_destino"] = col_venda

        return df_base

    except Exception as e:
        log_debug(f"Erro na precificação: {e}", "ERROR")
        return None


# ==========================================================
# UI
# ==========================================================
def render_precificacao(df_base):
    if not safe_df_dados(df_base):
        return

    df_base_calc = _garantir_base_precificacao(df_base)
    colunas = list(df_base_calc.columns)

    if not colunas:
        return

    st.markdown("### 💰 Precificação")

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

    df_saida_atual = st.session_state.get("df_saida", df_base_calc)

    df_precificado = _aplicar_precificacao(df_saida_atual.copy())

    if safe_df_dados(df_precificado):
        st.session_state["df_saida"] = df_precificado.copy()
        st.session_state["df_final"] = df_precificado.copy()
        df_preview = df_precificado
    else:
        df_preview = df_base_calc

    with st.expander("📊 Preview da precificação", expanded=True):
        st.dataframe(
            df_preview.head(10),
            use_container_width=True,
            hide_index=True,
        )
