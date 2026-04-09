from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_dados_estado import safe_df_dados


# ==========================================================
# MODELO
# ==========================================================
def obter_modelo_ativo():
    tipo = str(st.session_state.get("tipo_operacao_bling") or "").strip().lower()

    if tipo == "cadastro":
        return st.session_state.get("df_modelo_cadastro")

    if tipo == "estoque":
        return st.session_state.get("df_modelo_estoque")

    return None


def _modelo_tem_estrutura(df) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


# ==========================================================
# DF VÁLIDO (PRO)
# ==========================================================
def _df_valido_para_fluxo(df) -> bool:
    try:
        if not safe_df_dados(df):
            return False

        if not isinstance(df, pd.DataFrame):
            return False

        # aceita df vazio SOMENTE se for modelo
        if len(df.columns) == 0:
            return False

        return True
    except Exception:
        return False


# ==========================================================
# VALIDAÇÃO PRINCIPAL
# ==========================================================
def validar_antes_mapeamento() -> tuple[bool, list[str]]:
    erros: list[str] = []

    tipo = str(st.session_state.get("tipo_operacao_bling") or "").strip().lower()

    df_origem = st.session_state.get("df_origem")
    df_saida = st.session_state.get("df_saida")
    df_final = st.session_state.get("df_final")
    modelo_ativo = obter_modelo_ativo()

    # ======================================================
    # OPERAÇÃO
    # ======================================================
    if tipo not in {"cadastro", "estoque"}:
        erros.append("Selecione a operação antes de continuar.")

    # ======================================================
    # ORIGEM
    # ======================================================
    if not _df_valido_para_fluxo(df_origem):
        erros.append("A origem dos dados não está carregada corretamente.")

    # ======================================================
    # SAÍDA
    # ======================================================
    if not _df_valido_para_fluxo(df_saida):
        erros.append("A base de saída ainda não foi preparada.")

    # ======================================================
    # FINAL (AUTO CORREÇÃO)
    # ======================================================
    if _df_valido_para_fluxo(df_saida) and not _df_valido_para_fluxo(df_final):
        try:
            st.session_state["df_final"] = df_saida.copy()
            df_final = st.session_state.get("df_final")
        except Exception:
            pass

    if not _df_valido_para_fluxo(df_final):
        erros.append("A base final ainda não foi preparada corretamente.")

    # ======================================================
    # MODELO BLING
    # ======================================================
    if not _modelo_tem_estrutura(modelo_ativo):
        if tipo == "cadastro":
            erros.append("Anexe o modelo oficial de cadastro do Bling.")
        elif tipo == "estoque":
            erros.append("Anexe o modelo oficial de estoque do Bling.")
        else:
            erros.append("Anexe o modelo do Bling antes de continuar.")

    # ======================================================
    # RESULTADO
    # ======================================================
    return len(erros) == 0, erros
