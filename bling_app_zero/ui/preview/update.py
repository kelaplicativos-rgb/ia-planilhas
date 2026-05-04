from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import safe_df_estrutura
from bling_app_zero.ui.preview.merge import mesclar_preservando_manual
from bling_app_zero.ui.preview_final_data import garantir_df_final_canonico, zerar_colunas_video


def normalizar_preview(df_final: pd.DataFrame, tipo_operacao: str, deposito_nome: str) -> pd.DataFrame:
    manual = st.session_state.get("df_final")
    normalizado = garantir_df_final_canonico(df=df_final, tipo_operacao=tipo_operacao, deposito_nome=deposito_nome)
    normalizado = zerar_colunas_video(normalizado)
    resultado = mesclar_preservando_manual(normalizado, manual).fillna("")
    st.session_state["df_final"] = resultado
    return resultado


def obter_preview_atualizado(df_final: pd.DataFrame, tipo_operacao: str, deposito_nome: str) -> pd.DataFrame:
    atual = st.session_state.get("df_final", df_final)
    if not isinstance(atual, pd.DataFrame) or not safe_df_estrutura(atual):
        return df_final
    base = df_final.copy().fillna("") if isinstance(df_final, pd.DataFrame) else pd.DataFrame()
    manual = atual.copy().fillna("")
    base = garantir_df_final_canonico(
        df=base if safe_df_estrutura(base) else manual,
        tipo_operacao=tipo_operacao,
        deposito_nome=deposito_nome,
    )
    base = zerar_colunas_video(base)
    resultado = mesclar_preservando_manual(base, manual).fillna("")
    st.session_state["df_final"] = resultado
    return resultado
