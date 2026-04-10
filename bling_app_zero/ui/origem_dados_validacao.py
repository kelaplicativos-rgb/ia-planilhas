from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.core.modelos_bling import carregar_modelo_por_operacao
from bling_app_zero.ui.origem_dados_estado import safe_df_dados


def obter_modelo_ativo():
    tipo = str(st.session_state.get("tipo_operacao_bling") or "").strip().lower()

    if tipo == "cadastro":
        df = st.session_state.get("df_modelo_cadastro")
        if isinstance(df, pd.DataFrame) and len(df.columns) > 0:
            return df

        df = carregar_modelo_por_operacao("cadastro")
        st.session_state["df_modelo_cadastro"] = df.copy()
        return df

    if tipo == "estoque":
        df = st.session_state.get("df_modelo_estoque")
        if isinstance(df, pd.DataFrame) and len(df.columns) > 0:
            return df

        df = carregar_modelo_por_operacao("estoque")
        st.session_state["df_modelo_estoque"] = df.copy()
        return df

    return None


def _modelo_tem_estrutura(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def _df_valido_para_fluxo(df) -> bool:
    try:
        if not safe_df_dados(df):
            return False

        if not isinstance(df, pd.DataFrame):
            return False

        if len(df.columns) == 0:
            return False

        return True
    except Exception:
        return False


def validar_antes_mapeamento() -> tuple[bool, list[str]]:
    erros: list[str] = []

    tipo = str(st.session_state.get("tipo_operacao_bling") or "").strip().lower()
    df_origem = st.session_state.get("df_origem")
    df_saida = st.session_state.get("df_saida")
    df_final = st.session_state.get("df_final")
    modelo_ativo = obter_modelo_ativo()

    if tipo not in {"cadastro", "estoque"}:
        erros.append("Selecione a operação antes de continuar.")

    if not _df_valido_para_fluxo(df_origem):
        erros.append("A origem dos dados não está carregada corretamente.")

    if not _df_valido_para_fluxo(df_saida):
        erros.append("A base de saída ainda não foi preparada.")

    if _df_valido_para_fluxo(df_saida) and not _df_valido_para_fluxo(df_final):
        try:
            st.session_state["df_final"] = df_saida.copy()
            df_final = st.session_state.get("df_final")
        except Exception:
            pass

    if not _df_valido_para_fluxo(df_final):
        erros.append("A base final ainda não foi preparada corretamente.")

    if not _modelo_tem_estrutura(modelo_ativo):
        erros.append("O modelo interno do Bling não está disponível.")

    return len(erros) == 0, erros
