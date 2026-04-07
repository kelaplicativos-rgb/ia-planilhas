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


def _df_preview_seguro(df: pd.DataFrame | None) -> pd.DataFrame | None:
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


def coletar_parametros_precificacao():
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
            "valor unitário",
            "preco",
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


def render_precificacao(df_base):
    st.markdown("### Precificação")

    if not safe_df_dados(df_base):
        return

    colunas = list(df_base.columns)
    if not colunas:
        return

    coluna_preco_default = _detectar_coluna_preco_default(colunas)

    coluna_preco = st.selectbox(
        "Selecione a coluna de PREÇO DE CUSTO",
        options=colunas,
        index=coluna_preco_default,
        key="coluna_preco_base",
    )

    col1, col2 = st.columns(2)

    with col1:
        st.number_input("Margem (%)", min_value=0.0, key="margem_lucro")
        st.number_input("Impostos (%)", min_value=0.0, key="perc_impostos")

    with col2:
        st.number_input("Custo fixo", min_value=0.0, key="custo_fixo")
        st.number_input("Taxa extra (%)", min_value=0.0, key="taxa_extra")

    # =========================================================
    # 🔥 AUTO APLICAÇÃO (CORREÇÃO PRINCIPAL)
    # =========================================================
    params = coletar_parametros_precificacao()

    try:
        df_precificado = aplicar_precificacao_no_fluxo(df_base, params)

        if safe_df_dados(df_precificado):
            st.session_state["df_precificado"] = df_precificado.copy()

            # 🔥 trava campo preço no mapeamento
            st.session_state["bloquear_campos_auto"] = {
                "preco": True,
                "preço": True,
                "preco de venda": True,
                "preço de venda": True,
            }

    except Exception as e:
        log_debug(f"Erro na precificação automática: {e}", "ERRO")

    # =========================================================
    # BOTÃO MANUAL (mantido)
    # =========================================================
    if st.button("Reaplicar precificação", use_container_width=True):
        try:
            df_precificado = aplicar_precificacao_no_fluxo(df_base, params)

            st.session_state["df_precificado"] = df_precificado.copy()
            st.success("Precificação reaplicada com sucesso!")

        except Exception as e:
            log_debug(f"Erro ao reaplicar precificação: {e}", "ERRO")
            st.error("Erro ao aplicar a precificação.")

    # =========================================================
    # PRÉVIA
    # =========================================================
    df_precificado_state = st.session_state.get("df_precificado")

    if safe_df_dados(df_precificado_state):
        with st.expander("Prévia da precificação", expanded=False):
            try:
                st.dataframe(
                    _df_preview_seguro(df_precificado_state).head(10),
                    use_container_width=True,
                )
            except Exception as e:
                log_debug(f"Erro ao renderizar prévia: {e}", "ERRO")
