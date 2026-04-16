
from __future__ import annotations

import re
from typing import Any

import pandas as pd

from bling_app_zero.ui.app_dataframe import garantir_dataframe, safe_df_dados
from bling_app_zero.ui.app_formatters import to_float_brasil
from bling_app_zero.ui.app_text import normalizar_texto, safe_lower


def _somente_digitos(valor: Any) -> str:
    return re.sub(r"\D+", "", normalizar_texto(valor))


def _gtin_checksum_valido(gtin: str) -> bool:
    if not gtin.isdigit() or len(gtin) not in {8, 12, 13, 14}:
        return False

    digitos = [int(d) for d in gtin]
    digito_verificador = digitos[-1]
    corpo = digitos[:-1][::-1]

    total = 0
    for indice, digito in enumerate(corpo, start=1):
        peso = 3 if indice % 2 == 1 else 1
        total += digito * peso

    calculado = (10 - (total % 10)) % 10
    return calculado == digito_verificador


def limpar_gtin_invalido(valor: Any) -> str:
    gtin = _somente_digitos(valor)
    if _gtin_checksum_valido(gtin):
        return gtin
    return ""


def normalizar_imagens_pipe(valor: Any) -> str:
    texto = normalizar_texto(valor)
    if not texto:
        return ""

    texto = texto.replace("\n", "|").replace(";", "|")
    texto = re.sub(r"\s*\|\s*", "|", texto)
    texto = re.sub(r",(?=https?://)", "|", texto)
    texto = re.sub(r"\|+", "|", texto)

    partes = [p.strip() for p in texto.strip("| ").split("|") if p.strip()]
    vistos = set()
    saida = []

    for parte in partes:
        if parte not in vistos:
            vistos.add(parte)
            saida.append(parte)

    return "|".join(saida)


def normalizar_situacao(valor: Any, default: str = "Ativo") -> str:
    texto = normalizar_texto(valor)
    return texto if texto else default


def _coluna_vazia_ou_invalida(series: pd.Series) -> int:
    return (
        series.astype(str)
        .str.strip()
        .str.lower()
        .isin(["", "nan", "none", "nat", ""])
        .sum()
    )


def validar_df_para_download(
    df: pd.DataFrame,
    tipo_operacao_bling: str,
) -> tuple[bool, list[str]]:
    base = garantir_dataframe(df)
    erros: list[str] = []

    if not safe_df_dados(base):
        erros.append("A planilha final está vazia.")
        return False, erros

    tipo = safe_lower(tipo_operacao_bling)

    if tipo == "estoque":
        obrigatorias = [
            "Código",
            "Descrição",
            "Depósito (OBRIGATÓRIO)",
            "Balanço (OBRIGATÓRIO)",
            "Preço unitário (OBRIGATÓRIO)",
        ]
    else:
        obrigatorias = [
            "Código",
            "Descrição",
            "Preço de venda",
        ]

    for coluna in obrigatorias:
        if coluna not in base.columns:
            erros.append(f"Coluna obrigatória ausente: {coluna}")
            continue

        vazios = _coluna_vazia_ou_invalida(base[coluna])
        if vazios > 0:
            erros.append(f"Coluna obrigatória com valores vazios: {coluna} ({vazios})")

    if tipo == "estoque":
        if "Balanço (OBRIGATÓRIO)" in base.columns:
            invalidos = (
                pd.to_numeric(
                    base["Balanço (OBRIGATÓRIO)"].astype(str).str.replace(",", ".", regex=False),
                    errors="coerce",
                )
                .isna()
                .sum()
            )
            if invalidos > 0:
                erros.append(f"Balanço (OBRIGATÓRIO) contém valores inválidos ({invalidos})")
    else:
        if "Preço de venda" in base.columns:
            invalidos = (
                pd.to_numeric(
                    base["Preço de venda"]
                    .astype(str)
                    .str.replace(".", "", regex=False)
                    .str.replace(",", ".", regex=False),
                    errors="coerce",
                )
                .isna()
                .sum()
            )
            if invalidos > 0:
                erros.append(f"Preço de venda contém valores inválidos ({invalidos})")

    return len(erros) == 0, erros

