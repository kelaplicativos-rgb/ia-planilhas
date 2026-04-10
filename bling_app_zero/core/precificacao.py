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


def calcular_preco_venda(
    preco_compra: float,
    percentual_impostos: float,
    margem_lucro: float,
    custo_fixo: float,
    taxa_extra: float,
) -> float:
    base = 0.0

    try:
        base = max(0.0, _to_float(preco_compra) + _to_float(custo_fixo))

        impostos = _to_float(percentual_impostos) / 100.0
        lucro = _to_float(margem_lucro) / 100.0
        taxa = _to_float(taxa_extra) / 100.0

        denominador = 1.0 - impostos - lucro - taxa

        if denominador <= 0:
            return round(base, 2)

        resultado = base / denominador

        if resultado < base:
            resultado = base

        return round(resultado, 2)

    except Exception:
        return round(base, 2)


# ==========================================================
# 🔥 DETECTAR COLUNA DESTINO (CORRIGIDO)
# ==========================================================
def _detectar_coluna_preco_saida(df: pd.DataFrame) -> str:
    try:
        prioridades = [
            "preço de venda",
            "preco de venda",
            "valor de venda",
            "valor venda",
        ]

        # prioridade EXATA primeiro
        for p in prioridades:
            for col in df.columns:
                nome = str(col).strip().lower()
                if p == nome:
                    return col

        # fallback mais flexível
        for col in df.columns:
            nome = str(col).strip().lower()
            if "venda" in nome:
                return col

        # fallback final → usa a primeira coluna de preço encontrada
        for col in df.columns:
            nome = str(col).strip().lower()
            if "preço" in nome or "preco" in nome:
                return col

        return "Preço de venda"

    except Exception:
        return "Preço de venda"


# ==========================================================
# 🔥 APLICAÇÃO ROBUSTA
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

    # 🔥 fallback inteligente da coluna base
    if not coluna_preco or coluna_preco not in df_saida.columns:
        for col in df_saida.columns:
            nome = str(col).lower()
            if "custo" in nome or "compra" in nome:
                coluna_preco = col
                break

    if not coluna_preco or coluna_preco not in df_saida.columns:
        return df_saida  # sem base não calcula

    coluna_saida = _detectar_coluna_preco_saida(df_saida)

    precos_base = df_saida[coluna_preco].apply(_to_float)

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


# ==========================================================
# 🔥 FLUXO
# ==========================================================
def aplicar_precificacao_no_fluxo(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    try:
        df_precificado = aplicar_precificacao_automatica(
            df=df,
            coluna_preco=params.get("coluna_preco"),
            percentual_impostos=params.get("impostos", 0),
            margem_lucro=params.get("lucro", 0),
            custo_fixo=params.get("custo_fixo", 0),
            taxa_extra=params.get("taxa", 0),
        )

        return df_precificado

    except Exception:
        return df.copy()
