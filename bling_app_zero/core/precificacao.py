from __future__ import annotations

import re
from typing import Any

import pandas as pd


# ==========================================================
# BASE
# ==========================================================
def _to_float(valor: Any) -> float:
    if valor is None:
        return 0.0

    try:
        if pd.isna(valor):
            return 0.0
    except Exception:
        pass

    if isinstance(valor, (int, float)):
        try:
            return float(valor)
        except Exception:
            return 0.0

    texto = str(valor).strip()
    if not texto:
        return 0.0

    texto = (
        texto.replace("R$", "")
        .replace("r$", "")
        .replace(" ", "")
        .replace("\u00a0", "")
    )

    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", "")

    texto = re.sub(r"[^\d\.\-]", "", texto)

    try:
        return float(texto)
    except Exception:
        return 0.0


def _normalizar_nome_coluna(nome: str) -> str:
    try:
        texto = str(nome).strip().lower()
        texto = texto.replace("_", " ").replace("-", " ")
        texto = re.sub(r"\s+", " ", texto)
        return texto
    except Exception:
        return ""


# ==========================================================
# DETECÇÃO AUTOMÁTICA
# ==========================================================
def _detectar_coluna_preco(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return ""

    prioridades = [
        "preco custo",
        "preço custo",
        "preco de custo",
        "preço de custo",
        "valor custo",
        "valor de custo",
        "custo",
        "preco compra",
        "preço compra",
        "preco de compra",
        "preço de compra",
        "valor unitario",
        "valor unitário",
        "valor",
        "preco",
        "preço",
    ]

    colunas = {col: _normalizar_nome_coluna(col) for col in df.columns}

    for alvo in prioridades:
        for col, nome in colunas.items():
            if alvo == nome:
                return col

    for alvo in prioridades:
        for col, nome in colunas.items():
            if alvo in nome:
                return col

    return ""


def _detectar_coluna_venda(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return ""

    prioridades = [
        "preço de venda",
        "preco de venda",
        "valor de venda",
        "preço venda",
        "preco venda",
    ]

    colunas = {col: _normalizar_nome_coluna(col) for col in df.columns}

    for alvo in prioridades:
        for col, nome in colunas.items():
            if alvo == nome:
                return col

    for alvo in prioridades:
        for col, nome in colunas.items():
            if alvo in nome:
                return col

    return ""


# ==========================================================
# CÁLCULO
# ==========================================================
def calcular_preco_venda(
    preco_compra: float,
    percentual_impostos: float,
    margem_lucro: float,
    custo_fixo: float,
    taxa_extra: float,
) -> float:
    try:
        preco_compra = _to_float(preco_compra)
        percentual_impostos = _to_float(percentual_impostos)
        margem_lucro = _to_float(margem_lucro)
        custo_fixo = _to_float(custo_fixo)
        taxa_extra = _to_float(taxa_extra)

        base = max(0.0, preco_compra + custo_fixo)
        impostos = percentual_impostos / 100.0
        lucro = margem_lucro / 100.0
        taxa = taxa_extra / 100.0

        denominador = 1.0 - impostos - lucro - taxa

        # Nunca deixar a função zerar o preço por configuração inválida
        if denominador <= 0:
            return round(base, 2)

        resultado = base / denominador

        # Proteção adicional para nunca vender abaixo da base
        if resultado < base:
            resultado = base

        return round(max(0.0, float(resultado)), 2)

    except Exception:
        try:
            return round(max(0.0, _to_float(preco_compra) + _to_float(custo_fixo)), 2)
        except Exception:
            return 0.0


# ==========================================================
# APLICAÇÃO PRINCIPAL
# ==========================================================
def aplicar_precificacao_automatica(
    df: pd.DataFrame,
    coluna_preco: str | None = None,
    percentual_impostos: float = 0.0,
    margem_lucro: float = 0.0,
    custo_fixo: float = 0.0,
    taxa_extra: float = 0.0,
) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    df_saida = df.copy()

    coluna_base = (
        coluna_preco
        if coluna_preco and coluna_preco in df_saida.columns
        else _detectar_coluna_preco(df_saida)
    )

    if not coluna_base:
        return df_saida

    precos_base = df_saida[coluna_base].apply(_to_float)

    coluna_destino = _detectar_coluna_venda(df_saida)
    if not coluna_destino:
        coluna_destino = "Preço de venda"
        if coluna_destino not in df_saida.columns:
            df_saida[coluna_destino] = 0.0

    df_saida[coluna_destino] = precos_base.apply(
        lambda valor: calcular_preco_venda(
            preco_compra=valor,
            percentual_impostos=percentual_impostos,
            margem_lucro=margem_lucro,
            custo_fixo=custo_fixo,
            taxa_extra=taxa_extra,
        )
        if _to_float(valor) > 0
        else 0.0
    )

    return df_saida


# ==========================================================
# INTEGRA COM O FLUXO
# ==========================================================
def aplicar_precificacao_no_fluxo(
    df: pd.DataFrame,
    params: dict,
) -> pd.DataFrame:
    """
    Garante que a precificação atualiza o fluxo inteiro.
    """
    try:
        params = params if isinstance(params, dict) else {}

        df_precificado = aplicar_precificacao_automatica(
            df=df,
            coluna_preco=params.get("coluna_preco"),
            percentual_impostos=params.get("impostos", 0),
            margem_lucro=params.get("lucro", 0),
            custo_fixo=params.get("custo_fixo", 0),
            taxa_extra=params.get("taxa", 0),
        )

        try:
            import streamlit as st

            st.session_state["df_saida"] = df_precificado.copy()
            st.session_state["df_final"] = df_precificado.copy()
        except Exception:
            pass

        return df_precificado

    except Exception:
        return df.copy() if isinstance(df, pd.DataFrame) else pd.DataFrame()
