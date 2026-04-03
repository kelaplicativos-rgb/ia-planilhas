from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Union

import pandas as pd


ArquivoLike = Union[str, Path, BytesIO]


def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def limpar_valores_vazios(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.fillna("")

    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()

    return df


def ler_excel(arquivo: ArquivoLike) -> pd.DataFrame:
    df = pd.read_excel(arquivo, dtype=object)
    df = normalizar_colunas(df)
    df = limpar_valores_vazios(df)
    return df


def ler_csv(arquivo: ArquivoLike) -> pd.DataFrame:
    tentativas = [
        {"sep": ";", "encoding": "utf-8"},
        {"sep": ";", "encoding": "latin-1"},
        {"sep": ",", "encoding": "utf-8"},
        {"sep": ",", "encoding": "latin-1"},
    ]

    ultimo_erro = None

    for cfg in tentativas:
        try:
            df = pd.read_csv(
                arquivo,
                sep=cfg["sep"],
                encoding=cfg["encoding"],
                dtype=object,
            )
            df = normalizar_colunas(df)
            df = limpar_valores_vazios(df)
            return df
        except Exception as e:
            ultimo_erro = e

    raise ValueError(f"Não foi possível ler o CSV enviado: {ultimo_erro}")


def ler_planilha(arquivo: ArquivoLike) -> pd.DataFrame:
    nome = getattr(arquivo, "name", str(arquivo)).lower()

    if nome.endswith(".xlsx"):
        return ler_excel(arquivo)

    if nome.endswith(".csv"):
        return ler_csv(arquivo)

    raise ValueError("Formato não suportado. Use .xlsx ou .csv.")


def salvar_excel_bytes(df: pd.DataFrame, nome_aba: str = "Planilha") -> BytesIO:
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=nome_aba)

    output.seek(0)
    return output
