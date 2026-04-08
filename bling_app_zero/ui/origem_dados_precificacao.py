from __future__ import annotations

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
                try:
                    df_preview[col] = df_preview[col].astype(str)
                except Exception:
                    pass

        return df_preview.replace(
            {"nan": "", "None": "", "<NA>": "", "NaT": ""}
        )
    except Exception:
        return df


def coletar_parametros_precificacao() -> dict:
    return {
        "coluna_preco": st.session_state.get("coluna_preco_base"),
        "impostos": safe_float(st.session_state.get("perc_impostos", 0)),
        "lucro": safe_float(st.session_state.get("margem_lucro", 0)),
        "custo_fixo": safe_float(st.session_state.get("custo_fixo", 0)),
        "taxa": safe_float(st.session_state.get("taxa_extra", 0)),
    }


def _detectar_coluna_preco_default(colunas: list[str]) -> int:
    try:
        candidatos = [
            "preco de custo",
            "preço de custo",
            "custo",
            "valor custo",
            "preco compra",
            "preço compra",
            "preco de compra",
            "preço de compra",
            "valor unitário",
            "valor unitario",
            "preco",
            "preço",
            "valor",
        ]

        colunas_lower = [str(c).strip().lower() for c in colunas]

        for candidato in candidatos:
            for i, nome_col in enumerate(colunas_lower):
                if candidato in nome_col:
                    return i

        return 0
    except Exception:
        return 0


# 🔥 NOVO: aplicar no fluxo SEM destruir origem
def _aplicar_precificacao(df_base: pd.DataFrame) -> pd.DataFrame | None:
    try:
        params = coletar_parametros_precificacao()

        coluna_preco = str(params.get("coluna_preco") or "").strip()
        if not coluna_preco:
            return None

        if coluna_preco not in list(df_base.columns):
            log_debug(
                f"Coluna inválida na precificação: {coluna_preco}",
                "ERRO",
            )
            return None

        df_precificado = aplicar_precificacao_no_fluxo(df_base.copy(), params)

        if not safe_df_dados(df_precificado):
            return None

        return df_precificado

    except Exception as e:
        log_debug(f"Erro na precificação: {e}", "ERRO")
        return None


def render_precificacao(df_base):
    if not safe_df_dados(df_base):
        return

    # 🔥 USAR DF ATUAL DO FLUXO
    df_fluxo = st.session_state.get("df_saida", df_base)

    colunas = list(df_fluxo.columns)
    if not colunas:
        return

    coluna_preco_default = _detectar_coluna_preco_default(colunas)

    st.selectbox(
        "Coluna de custo",
        options=colunas,
        index=coluna_preco_default,
        key="coluna_preco_base",
    )

    col1, col2 = st.columns(2)

    with col1:
        st.number_input(
            "Margem (%)",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            key="margem_lucro",
        )
        st.number_input(
            "Impostos (%)",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            key="perc_impostos",
        )

    with col2:
        st.number_input(
            "Custo fixo",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            key="custo_fixo",
        )
        st.number_input(
            "Taxa (%)",
            min_value=0.0,
            step=0.01,
            format="%.2f",
            key="taxa_extra",
        )

    # 🔥 recalculo automático SEM botão
    df_precificado = _aplicar_precificacao(df_fluxo)

    if safe_df_dados(df_precificado):
        # 🔥 ATUALIZA SOMENTE DF DE SAÍDA
        st.session_state["df_saida"] = df_precificado.copy()
        st.session_state["df_final"] = df_precificado.copy()

    df_preview = df_precificado or df_fluxo

    if safe_df_dados(df_preview):
        with st.expander("📊 Preview da precificação", expanded=True):
            st.dataframe(
                _df_preview_seguro(df_preview).head(10),
                use_container_width=True,
                hide_index=True,
            )
