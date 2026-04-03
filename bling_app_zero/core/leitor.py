from utils.excel import (
    ler_planilha,
    limpar_valores_vazios,
    normalizar_colunas,
)

import pandas as pd


def carregar_planilha(arquivo) -> pd.DataFrame:
    """
    Pipeline completo:
    - lê
    - normaliza colunas
    - limpa valores
    """

    df = ler_planilha(arquivo)

    df = normalizar_colunas(df)

    df = limpar_valores_vazios(df)

    return df


def validar_planilha_vazia(df: pd.DataFrame) -> bool:
    """
    Verifica se a planilha está vazia
    """
    return df.empty or len(df.columns) == 0


def preview(df: pd.DataFrame, linhas: int = 5) -> pd.DataFrame:
    """
    Retorna preview para UI
    """
    return df.head(linhas)
