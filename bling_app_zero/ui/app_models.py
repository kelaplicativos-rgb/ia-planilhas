
from __future__ import annotations

from typing import Any

import pandas as pd

from bling_app_zero.ui.app_dataframe import garantir_dataframe
from bling_app_zero.ui.app_formatters import formatar_inteiro_seguro, formatar_numero_bling
from bling_app_zero.ui.app_text import normalizar_texto, safe_lower
from bling_app_zero.ui.app_validators import (
    limpar_gtin_invalido,
    normalizar_imagens_pipe,
    normalizar_situacao,
)


def colunas_modelo_estoque() -> list[str]:
    return [
        "Código",
        "Descrição",
        "Depósito (OBRIGATÓRIO)",
        "Balanço (OBRIGATÓRIO)",
        "Preço unitário (OBRIGATÓRIO)",
        "Situação",
    ]


def colunas_modelo_cadastro() -> list[str]:
    return [
        "Código",
        "Descrição",
        "Descrição Curta",
        "Preço de venda",
        "GTIN/EAN",
        "Situação",
        "URL Imagens",
        "Categoria",
    ]


def obter_colunas_modelo_por_tipo(tipo_operacao_bling: str) -> list[str]:
    if safe_lower(tipo_operacao_bling) == "estoque":
        return colunas_modelo_estoque()
    return colunas_modelo_cadastro()


def garantir_colunas_modelo(
    df: pd.DataFrame,
    tipo_operacao_bling: str,
) -> pd.DataFrame:
    base = garantir_dataframe(df)
    colunas = obter_colunas_modelo_por_tipo(tipo_operacao_bling)

    for coluna in colunas:
        if coluna not in base.columns:
            base[coluna] = ""

    base = base[colunas].copy()
    return base.fillna("")


def blindar_df_para_bling(
    df: pd.DataFrame,
    tipo_operacao_bling: str,
    deposito_nome: str = "",
) -> pd.DataFrame:
    base = garantir_dataframe(df)
    tipo = safe_lower(tipo_operacao_bling)

    if tipo == "estoque":
        base = garantir_colunas_modelo(base, "estoque")

        if deposito_nome:
            base["Depósito (OBRIGATÓRIO)"] = normalizar_texto(deposito_nome)

        base["Código"] = base["Código"].apply(normalizar_texto)
        base["Descrição"] = base["Descrição"].apply(normalizar_texto)
        base["Depósito (OBRIGATÓRIO)"] = base["Depósito (OBRIGATÓRIO)"].apply(normalizar_texto)
        base["Balanço (OBRIGATÓRIO)"] = base["Balanço (OBRIGATÓRIO)"].apply(formatar_inteiro_seguro)
        base["Preço unitário (OBRIGATÓRIO)"] = base["Preço unitário (OBRIGATÓRIO)"].apply(formatar_numero_bling)
        base["Situação"] = base["Situação"].apply(normalizar_situacao)
    else:
        base = garantir_colunas_modelo(base, "cadastro")

        base["Código"] = base["Código"].apply(normalizar_texto)
        base["Descrição"] = base["Descrição"].apply(normalizar_texto)
        base["Descrição Curta"] = base["Descrição Curta"].apply(normalizar_texto)
        base["Preço de venda"] = base["Preço de venda"].apply(formatar_numero_bling)
        base["GTIN/EAN"] = base["GTIN/EAN"].apply(limpar_gtin_invalido)
        base["Situação"] = base["Situação"].apply(normalizar_situacao)
        base["URL Imagens"] = base["URL Imagens"].apply(normalizar_imagens_pipe)
        base["Categoria"] = base["Categoria"].apply(normalizar_texto)

    return base.fillna("")
