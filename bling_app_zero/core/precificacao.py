from __future__ import annotations

import re

import pandas as pd


# ==========================================================
# BASE
# ==========================================================
def _to_float(valor) -> float:
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
# DETECÇÃO AUTOMÁTICA DE COLUNA DE CUSTO
# ==========================================================
def _detectar_coluna_preco(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return ""

    prioridades_exatas = [
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

    colunas_normalizadas = {
        col: _normalizar_nome_coluna(col)
        for col in df.columns
    }

    for alvo in prioridades_exatas:
        for col, nome in colunas_normalizadas.items():
            if alvo == nome:
                return col

    for alvo in prioridades_exatas:
        for col, nome in colunas_normalizadas.items():
            if alvo in nome:
                return col

    return ""


# ==========================================================
# DETECTAR COLUNA DE VENDA
# ==========================================================
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

    colunas_normalizadas = {
        col: _normalizar_nome_coluna(col)
        for col in df.columns
    }

    for alvo in prioridades:
        for col, nome in colunas_normalizadas.items():
            if alvo == nome:
                return col

    for alvo in prioridades:
        for col, nome in colunas_normalizadas.items():
            if alvo in nome:
                return col

    return ""


# ==========================================================
# CÁLCULO BASE
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

        base = preco_compra + custo_fixo
        impostos = percentual_impostos / 100.0
        lucro = margem_lucro / 100.0
        taxa = taxa_extra / 100.0

        denominador = 1.0 - impostos - lucro - taxa
        if denominador <= 0:
            return 0.0

        resultado = base / denominador

        if resultado < 0:
            return 0.0

        return float(resultado)

    except Exception:
        return 0.0


# ==========================================================
# APLICAÇÃO AUTOMÁTICA NO DF
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

    if coluna_preco and coluna_preco in df_saida.columns:
        coluna_base = coluna_preco
    else:
        coluna_base = _detectar_coluna_preco(df_saida)

    if not coluna_base:
        return df_saida

    precos_base = df_saida[coluna_base].apply(_to_float)

    coluna_destino = _detectar_coluna_venda(df_saida)
    if not coluna_destino:
        coluna_destino = "Preço de venda"
        if coluna_destino not in df_saida.columns:
            df_saida[coluna_destino] = 0.0

    df_saida[coluna_destino] = precos_base.apply(
        lambda valor: round(
            calcular_preco_venda(
                preco_compra=valor,
                percentual_impostos=percentual_impostos,
                margem_lucro=margem_lucro,
                custo_fixo=custo_fixo,
                taxa_extra=taxa_extra,
            ),
            2,
        )
        if _to_float(valor) > 0
        else 0.0
    )

    return df_saida


# ==========================================================
# COMPATIBILIDADE ANTIGA
# ==========================================================
def calcular_preco_venda_df(
    df: pd.DataFrame,
    coluna_preco_base: str,
    percentual_impostos: float,
    margem_lucro: float,
    custo_fixo: float,
    taxa_extra: float,
    nome_coluna_saida: str = "preco",
    arredondar: int = 2,
) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()

    df_saida = df.copy()

    if coluna_preco_base not in df_saida.columns:
        return df_saida

    precos_base = df_saida[coluna_preco_base].apply(_to_float)

    df_saida[nome_coluna_saida] = precos_base.apply(
        lambda valor: round(
            calcular_preco_venda(
                preco_compra=valor,
                percentual_impostos=percentual_impostos,
                margem_lucro=margem_lucro,
                custo_fixo=custo_fixo,
                taxa_extra=taxa_extra,
            ),
            arredondar,
        )
        if _to_float(valor) > 0
        else 0.0
    )

    return df_saida
