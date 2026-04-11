from __future__ import annotations

import re
from typing import Any

import pandas as pd


def _to_float(valor: Any) -> float:
    if valor is None:
        return 0.0

    try:
        if pd.isna(valor):
            return 0.0
    except Exception:
        pass

    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()
    if not texto:
        return 0.0

    texto = texto.replace("R$", "").replace("r$", "").replace("\u00a0", " ").strip()
    texto = re.sub(r"\s+", "", texto)

    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", "")

    texto = re.sub(r"[^0-9.\-]", "", texto)

    try:
        return float(texto)
    except Exception:
        return 0.0


def calcular_preco_venda(
    preco_compra: float,
    percentual_impostos: float,
    margem_lucro: float,
    custo_fixo: float,
    taxa_extra: float,
) -> float:
    try:
        preco_base = max(0.0, _to_float(preco_compra))
        custo_fixo_val = max(0.0, _to_float(custo_fixo))
        impostos = max(0.0, _to_float(percentual_impostos)) / 100.0
        lucro = max(0.0, _to_float(margem_lucro)) / 100.0
        taxa = max(0.0, _to_float(taxa_extra)) / 100.0

        base = preco_base + custo_fixo_val
        denominador = 1.0 - impostos - lucro - taxa

        if denominador <= 0:
            return round(base, 2)

        resultado = base / denominador
        if resultado < base:
            resultado = base

        return round(resultado, 2)
    except Exception:
        return round(max(0.0, _to_float(preco_compra)), 2)


def _norm(nome: Any) -> str:
    try:
        return str(nome).strip().lower()
    except Exception:
        return ""


def _is_coluna_custo(nome: Any) -> bool:
    nome = _norm(nome)
    return (
        "custo" in nome
        or "compra" in nome
        or nome in {
            "preço de custo",
            "preco de custo",
            "preço de compra",
            "preco de compra",
            "valor custo",
            "valor de custo",
        }
    )


def _is_coluna_venda(nome: Any) -> bool:
    nome = _norm(nome)

    if nome in {
        "preço de venda",
        "preco de venda",
        "valor venda",
        "valor de venda",
        "preço unitário (obrigatório)",
        "preco unitario (obrigatorio)",
        "preço unitário",
        "preco unitario",
    }:
        return True

    if "venda" in nome:
        return True

    if ("unitário" in nome or "unitario" in nome) and ("preço" in nome or "preco" in nome):
        return True

    return False


def _detectar_coluna_preco_saida(df: pd.DataFrame, coluna_preco_base: str | None = None) -> str:
    try:
        prioridades = [
            "preço de venda",
            "preco de venda",
            "valor de venda",
            "valor venda",
            "preço unitário (obrigatório)",
            "preco unitario (obrigatorio)",
            "preço unitário",
            "preco unitario",
        ]

        base_norm = _norm(coluna_preco_base)

        for prioridade in prioridades:
            for col in df.columns:
                nome = _norm(col)
                if nome == prioridade and nome != base_norm and not _is_coluna_custo(nome):
                    return col

        for col in df.columns:
            nome = _norm(col)
            if _is_coluna_venda(nome) and nome != base_norm and not _is_coluna_custo(nome):
                return col

        return "Preço de venda"
    except Exception:
        return "Preço de venda"


def _detectar_coluna_preco_base(df: pd.DataFrame, coluna_preco: str | None = None) -> str | None:
    try:
        if coluna_preco and coluna_preco in df.columns:
            return coluna_preco

        prioridades = [
            "preço de custo",
            "preco de custo",
            "preço de compra",
            "preco de compra",
            "custo",
            "valor custo",
            "valor de custo",
        ]

        for prioridade in prioridades:
            for col in df.columns:
                if _norm(col) == prioridade:
                    return col

        for col in df.columns:
            if _is_coluna_custo(col):
                return col

        return None
    except Exception:
        return None


def aplicar_precificacao_automatica(
    df: pd.DataFrame,
    coluna_preco: str | None = None,
    percentual_impostos: float = 0.0,
    margem_lucro: float = 0.0,
    custo_fixo: float = 0.0,
    taxa_extra: float = 0.0,
) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    df_saida = df.copy()

    coluna_preco_base = _detectar_coluna_preco_base(df_saida, coluna_preco)
    if not coluna_preco_base or coluna_preco_base not in df_saida.columns:
        return df_saida

    coluna_saida = _detectar_coluna_preco_saida(df_saida, coluna_preco_base)

    if _norm(coluna_saida) == _norm(coluna_preco_base):
        coluna_saida = "Preço de venda"

    if coluna_saida not in df_saida.columns:
        df_saida[coluna_saida] = ""

    precos_base = df_saida[coluna_preco_base].apply(_to_float)

    df_saida[coluna_saida] = precos_base.apply(
        lambda valor: calcular_preco_venda(
            preco_compra=valor,
            percentual_impostos=percentual_impostos,
            margem_lucro=margem_lucro,
            custo_fixo=custo_fixo,
            taxa_extra=taxa_extra,
        )
        if valor > 0
        else 0.0
    )

    return df_saida


def aplicar_precificacao_no_fluxo(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    try:
        return aplicar_precificacao_automatica(
            df=df,
            coluna_preco=params.get("coluna_preco"),
            percentual_impostos=params.get("impostos", 0),
            margem_lucro=params.get("lucro", 0),
            custo_fixo=params.get("custo_fixo", 0),
            taxa_extra=params.get("taxa", 0),
        )
    except Exception:
        return df.copy()
