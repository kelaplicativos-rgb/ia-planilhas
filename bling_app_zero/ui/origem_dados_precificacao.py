from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.precificacao import aplicar_precificacao_automatica
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

        df_preview = df_preview.replace(
            {
                "nan": "",
                "None": "",
                "<NA>": "",
                "NaT": "",
            }
        )

        return df_preview
    except Exception:
        return df


def coletar_parametros_precificacao():
    return {
        "percentual_impostos": safe_float(st.session_state.get("perc_impostos", 0)),
        "margem_lucro": safe_float(st.session_state.get("margem_lucro", 0)),
        "custo_fixo": safe_float(st.session_state.get("custo_fixo", 0)),
        "taxa_extra": safe_float(st.session_state.get("taxa_extra", 0)),
    }


def aplicar_precificacao_com_fallback(df_base, coluna_preco):
    kwargs = coletar_parametros_precificacao()

    try:
        return aplicar_precificacao_automatica(
            df_base.copy(),
            coluna_preco=coluna_preco,
            **kwargs,
        )
    except TypeError:
        return aplicar_precificacao_automatica(
            df_base.copy(),
            **kwargs,
        )


def _detectar_coluna_preco_default(colunas: list[str]) -> int:
    try:
        candidatos = [
            "preco de custo",
            "preço de custo",
            "preco_custo",
            "preço_custo",
            "custo",
            "valor custo",
            "valor_custo",
            "preco compra",
            "preço compra",
            "preco_compra_xml",
            "preço compra xml",
            "valor unitário",
            "valor unitario",
            "preco",
            "preço",
            "valor",
        ]

        colunas_lower = [str(c).strip().lower() for c in colunas]

        for candidato in candidatos:
            for i, nome_col in enumerate(colunas_lower):
                if candidato == nome_col or candidato in nome_col:
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

    recalcular = st.button(
        "Aplicar precificação",
        use_container_width=True,
        key="btn_aplicar_precificacao",
    )

    if recalcular:
        try:
            df_precificado = aplicar_precificacao_com_fallback(df_base, coluna_preco)

            if safe_df_dados(df_precificado):
                st.session_state["df_precificado"] = df_precificado.copy()
                st.session_state["df_saida"] = df_precificado.copy()
                st.session_state["df_final"] = df_precificado.copy()
                st.session_state["bloquear_campos_auto"] = {"preco": True}
                log_debug(
                    f"Precificação aplicada com sucesso usando a coluna '{coluna_preco}'"
                )
            else:
                st.error("A precificação não retornou dados válidos.")
                log_debug("Precificação retornou DataFrame inválido", "ERRO")
        except Exception as e:
            log_debug(f"Erro na precificação: {e}", "ERRO")
            st.error("Erro ao aplicar a precificação.")

    df_preview_precificacao = st.session_state.get("df_precificado")
    if safe_df_dados(df_preview_precificacao):
        with st.expander("Prévia da precificação", expanded=False):
            try:
                st.dataframe(
                    _df_preview_seguro(df_preview_precificacao).head(10),
                    use_container_width=True,
                )
            except Exception as e:
                log_debug(f"Erro ao renderizar prévia da precificação: {e}", "ERRO")
                try:
                    st.write(_df_preview_seguro(df_preview_precificacao).head(10))
                except Exception:
                    pass
