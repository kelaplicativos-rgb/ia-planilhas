from __future__ import annotations

from io import BytesIO
from typing import Union

import pandas as pd


ArquivoExcel = Union[str, BytesIO]


def ler_excel(arquivo: ArquivoExcel, dtype=str) -> pd.DataFrame:
    """
    Lê arquivo Excel (.xlsx) e retorna DataFrame.

    Parâmetros:
        arquivo: caminho do arquivo ou objeto em memória
        dtype: tipo padrão das colunas (str por padrão para evitar perdas)

    Retorno:
        pandas.DataFrame
    """
    df = pd.read_excel(arquivo, dtype=dtype)
    return df


def salvar_excel(df: pd.DataFrame) -> BytesIO:
    """
    Salva um DataFrame em memória como arquivo Excel (.xlsx).

    Retorno:
        BytesIO pronto para download no Streamlit.
    """
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    output.seek(0)
    return output


def limpar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Faz limpeza básica segura no DataFrame:
    - remove colunas totalmente vazias
    - remove linhas totalmente vazias
    - converte nomes de colunas para string
    - remove espaços extras dos nomes de colunas
    """
    df = df.copy()

    df.columns = [str(col).strip() for col in df.columns]
    df = df.dropna(axis=1, how="all")
    df = df.dropna(axis=0, how="all")

    return df


def normalizar_texto(valor) -> str:
    """
    Normaliza valor para texto seguro.
    """
    if pd.isna(valor):
        return ""
    return str(valor).strip()


def aplicar_normalizacao_texto(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica normalização de texto em todas as células do DataFrame.
    """
    df = df.copy()
    for col in df.columns:
        df[col] = df[col].apply(normalizar_texto)
    return df
