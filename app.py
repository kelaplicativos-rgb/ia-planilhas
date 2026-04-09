from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.ui.origem_dados_estado import safe_df_dados


# ==========================================================
# MODELO
# ==========================================================
def obter_modelo_ativo() -> pd.DataFrame | None:
    tipo = str(st.session_state.get("tipo_operacao_bling") or "").strip().lower()

    if tipo == "cadastro":
        df = st.session_state.get("df_modelo_cadastro")
        return df if isinstance(df, pd.DataFrame) else None

    if tipo == "estoque":
        df = st.session_state.get("df_modelo_estoque")
        return df if isinstance(df, pd.DataFrame) else None

    return None


def _modelo_tem_estrutura(df: Any) -> bool:
    try:
        return isinstance(df, pd.DataFrame) and len(df.columns) > 0
    except Exception:
        return False


# ==========================================================
# DF VÁLIDO (PRO)
# ==========================================================
def _df_valido_para_fluxo(df: Any) -> bool:
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


def _montar_base_saida_vazia(
    df_origem: pd.DataFrame | None,
    modelo_ativo: pd.DataFrame | None,
) -> pd.DataFrame | None:
    """
    Monta uma base de saída fiel ao modelo Bling, mantendo apenas os cabeçalhos
    e replicando a quantidade de linhas da origem para o fluxo seguir sem cair.
    """
    try:
        if not _df_valido_para_fluxo(df_origem):
            return None

        if not _modelo_tem_estrutura(modelo_ativo):
            return None

        qtd_linhas = len(df_origem.index)
        colunas_modelo = [str(col) for col in modelo_ativo.columns.tolist()]

        df_base = pd.DataFrame(index=range(qtd_linhas), columns=colunas_modelo)

        # Blindagem da coluna ID: nunca preencher automaticamente.
        for col in df_base.columns:
            nome = str(col).strip().lower()
            if nome == "id":
                df_base[col] = ""

        return df_base
    except Exception:
        return None


def _garantir_bases_fluxo() -> None:
    """
    Auto corrige df_saida e df_final quando possível, usando a origem + modelo ativo.
    Isso evita queda do fluxo entre origem -> mapeamento.
    """
    try:
        df_origem = st.session_state.get("df_origem")
        df_saida = st.session_state.get("df_saida")
        df_final = st.session_state.get("df_final")
        modelo_ativo = obter_modelo_ativo()

        base_vazia = _montar_base_saida_vazia(df_origem, modelo_ativo)

        if base_vazia is None:
            return

        if not _df_valido_para_fluxo(df_saida):
            st.session_state["df_saida"] = base_vazia.copy()
            df_saida = st.session_state.get("df_saida")

        if _df_valido_para_fluxo(df_saida) and not _df_valido_para_fluxo(df_final):
            st.session_state["df_final"] = df_saida.copy()
    except Exception:
        pass


# ==========================================================
# VALIDAÇÃO PRINCIPAL
# ==========================================================
def validar_antes_mapeamento() -> tuple[bool, list[str]]:
    erros: list[str] = []

    tipo = str(st.session_state.get("tipo_operacao_bling") or "").strip().lower()

    # tenta auto corrigir antes de validar
    _garantir_bases_fluxo()

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
    # SAÍDA
    # ======================================================
    if not _df_valido_para_fluxo(df_saida):
        erros.append("A base de saída ainda não foi preparada.")

    # ======================================================
    # FINAL
    # ======================================================
    if not _df_valido_para_fluxo(df_final):
        erros.append("A base final ainda não foi preparada corretamente.")

    # ======================================================
    # RESULTADO
    # ======================================================
    return len(erros) == 0, erros
