from __future__ import annotations

import pandas as pd
import streamlit as st

from bling_app_zero.ui.app_helpers import safe_df_dados, safe_df_estrutura
from bling_app_zero.ui.precificacao.calc import calcular_preco, fmt_planilha, norm


CANDIDATOS_PRECO = [
    "Preço de venda", "Preco de venda", "Preço unitário (OBRIGATÓRIO)",
    "Preço unitário", "Preco unitario", "Preço", "Preco", "Valor",
]


def obter_base() -> pd.DataFrame:
    for key in ("df_precificado", "df_preview_inteligente", "df_saida", "df_origem"):
        df = st.session_state.get(key)
        if safe_df_dados(df):
            return df.copy().fillna("").reset_index(drop=True)
    return pd.DataFrame()


def achar_coluna(df: pd.DataFrame, candidatos: list[str]) -> str:
    if not safe_df_estrutura(df):
        return ""
    mapa = {norm(c): str(c) for c in df.columns}
    for candidato in candidatos:
        found = mapa.get(norm(candidato))
        if found:
            return found
    return ""


def detectar_coluna_custo(df: pd.DataFrame) -> str:
    candidatos = [
        "Preço de custo", "Preco de custo", "Preço custo", "Preco custo",
        "Custo", "Valor custo", "Preço unitário (OBRIGATÓRIO)",
        "Preço unitário", "Preço de venda", "Preço", "Preco", "Valor",
    ]
    found = achar_coluna(df, candidatos)
    if found:
        return found
    for col in df.columns:
        n = norm(col)
        if any(token in n for token in ("custo", "preco", "valor", "price")):
            return str(col)
    return ""


def coluna_preco_destino(df: pd.DataFrame) -> str:
    operacao = str(st.session_state.get("tipo_operacao", "cadastro") or "cadastro").strip().lower()
    if operacao == "estoque":
        found = achar_coluna(df, ["Preço unitário (OBRIGATÓRIO)", "Preço unitário", "Preco unitario", "Preço", "Preco"])
        return found or "Preço unitário (OBRIGATÓRIO)"
    found = achar_coluna(df, CANDIDATOS_PRECO)
    return found or "Preço de venda"


def aplicar_precificacao(df: pd.DataFrame, coluna_custo: str, valores: dict[str, float]) -> pd.DataFrame:
    if not safe_df_dados(df):
        return pd.DataFrame()
    base = df.copy().fillna("")
    if not coluna_custo or coluna_custo not in base.columns:
        return base
    destino = coluna_preco_destino(base)
    calculado = base[coluna_custo].apply(lambda custo: calcular_preco(custo, valores))
    base[destino] = calculado.apply(fmt_planilha)
    base["Preço calculado"] = calculado.apply(fmt_planilha)
    return base.fillna("")


def preparar_para_mapeamento(df: pd.DataFrame) -> None:
    base = df.copy().fillna("").reset_index(drop=True)
    st.session_state["df_precificado"] = base.copy()
    st.session_state["df_saida"] = base.copy()
    st.session_state.pop("df_final", None)
    st.session_state["pricing_fluxo_pronto"] = True
