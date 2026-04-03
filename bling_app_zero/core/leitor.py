import pandas as pd

from ..utils.excel import (
    ler_planilha,
    limpar_valores_vazios,
    normalizar_colunas,
)


def carregar_planilha(arquivo) -> pd.DataFrame:
    df = ler_planilha(arquivo)
    df = normalizar_colunas(df)
    df = limpar_valores_vazios(df)
    return df


def validar_planilha_vazia(df: pd.DataFrame) -> bool:
    return df.empty or len(df.columns) == 0


def preview(df: pd.DataFrame, linhas: int = 5) -> pd.DataFrame:
    return df.head(linhas)
