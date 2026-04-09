from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_dados_estado import safe_df_dados


def _df_tem_estrutura(df) -> bool:
    """
    Para modelo Bling, basta ter colunas válidas.
    Não exige linhas preenchidas, porque muitos modelos oficiais
    vêm apenas com o cabeçalho.
    """
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


def obter_modelo_ativo():
    tipo = str(st.session_state.get("tipo_operacao_bling") or "").strip().lower()

    if tipo == "cadastro":
        return st.session_state.get("df_modelo_cadastro")

    if tipo == "estoque":
        return st.session_state.get("df_modelo_estoque")

    return None


def validar_antes_mapeamento() -> tuple[bool, list[str]]:
    erros: list[str] = []

    tipo = str(st.session_state.get("tipo_operacao_bling") or "").strip().lower()
    df_origem = st.session_state.get("df_origem")
    df_saida = st.session_state.get("df_saida")
    df_final = st.session_state.get("df_final")
    modelo_ativo = obter_modelo_ativo()

    if tipo not in {"cadastro", "estoque"}:
        erros.append("Selecione a operação antes de continuar.")

    if not safe_df_dados(df_origem):
        erros.append("A origem dos dados não está carregada.")

    if not safe_df_dados(df_saida):
        erros.append("A base de saída ainda não foi preparada.")

    if safe_df_dados(df_saida) and not safe_df_dados(df_final):
        try:
            st.session_state["df_final"] = df_saida.copy()
            df_final = st.session_state.get("df_final")
        except Exception:
            pass

    if not safe_df_dados(df_final):
        erros.append("A base final ainda não foi preparada.")

    # MODELO BLING:
    # aqui a validação correta é por estrutura (colunas),
    # e não por quantidade de linhas.
    if not _df_tem_estrutura(modelo_ativo):
        if tipo == "cadastro":
            erros.append("Anexe o modelo oficial de cadastro do Bling.")
        elif tipo == "estoque":
            erros.append("Anexe o modelo oficial de estoque do Bling.")
        else:
            erros.append("Anexe o modelo oficial do Bling antes de continuar.")

    return len(erros) == 0, erros
