from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.origem_dados_estado import safe_df_dados


def validar_antes_mapeamento() -> tuple[bool, list[str]]:
    erros: list[str] = []

    tipo = str(st.session_state.get("tipo_operacao_bling") or "").strip().lower()
    df_origem = st.session_state.get("df_origem")
    df_saida = st.session_state.get("df_saida")
    df_final = st.session_state.get("df_final")

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

    if tipo == "cadastro":
        modelo_ok = safe_df_dados(st.session_state.get("df_modelo_cadastro"))
        if not modelo_ok:
            erros.append("Anexe o modelo oficial de cadastro do Bling.")
    elif tipo == "estoque":
        modelo_ok = safe_df_dados(st.session_state.get("df_modelo_estoque"))
        if not modelo_ok:
            erros.append("Anexe o modelo oficial de estoque do Bling.")

    return len(erros) == 0, erros


def obter_modelo_ativo():
    tipo = str(st.session_state.get("tipo_operacao_bling") or "").strip().lower()
    if tipo == "cadastro":
        return st.session_state.get("df_modelo_cadastro")
    if tipo == "estoque":
        return st.session_state.get("df_modelo_estoque")
    return None
