from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_dados_estado import (
    controlar_troca_operacao,
    controlar_troca_origem,
    safe_df_dados,
    sincronizar_estado_com_origem,
)
from bling_app_zero.ui.origem_dados_helpers import log_debug
from bling_app_zero.ui.origem_dados_precificacao import render_precificacao
from bling_app_zero.ui.origem_dados_uploads import (
    render_modelo_bling,
    render_origem_entrada,
)
from bling_app_zero.ui.origem_dados_validacao import (
    obter_modelo_ativo,
    validar_antes_mapeamento,
)


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


def render_origem_dados() -> None:
    etapa_atual = st.session_state.get("etapa_origem")
    if etapa_atual in ["mapeamento", "final"]:
        return

    st.subheader("Origem dos dados")

    operacao = st.radio(
        "Selecione a operação",
        ["Cadastro de Produtos", "Atualização de Estoque"],
        key="tipo_operacao",
    )

    controlar_troca_operacao(operacao, log_debug)

    if operacao == "Cadastro de Produtos":
        st.session_state["tipo_operacao_b
