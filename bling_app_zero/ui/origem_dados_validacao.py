from __future__ import annotations

import streamlit as st

from bling_app_zero.ui.origem_dados_estado import safe_df_dados


def validar_antes_mapeamento() -> tuple[bool, list[str]]:
    erros: list[str] = []

    if not safe_df_dados(st.session_state.get("df_origem")):
        erros.append("A origem dos dados não está carregada.")

    if not safe_df_dados(st.session_state.get("df_saida")):
        erros.append("A base de saída ainda não foi preparada.")

    tipo = st.session_state.get("tipo_operacao_bling")
    if tipo == "cadastro":
        modelo_ok = safe_df_dados(st.session_state.get("df_modelo_cadastro"))
        if not modelo_ok:
            erros.append("Anexe o modelo oficial de cadastro do Bling.")
    else:
        modelo_ok = safe_df_dados(st.session_state.get("df_modelo_estoque"))
        if not modelo_ok:
            erros.append("Anexe o modelo oficial de estoque do Bling.")

    return len(erros) == 0, erros


def obter_modelo_ativo():
    tipo = st.session_state.get("tipo_operacao_bling")
    if tipo == "cadastro":
        return st.session_state.get("df_modelo_cadastro")
    return st.session_state.get("df_modelo_estoque")
