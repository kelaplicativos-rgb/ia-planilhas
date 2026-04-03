from __future__ import annotations

import pandas as pd
import re


def limpar_texto(valor) -> str:
    """
    Limpeza pesada de texto:
    - remove espaços extras
    - remove quebras de linha
    - remove caracteres invisíveis
    """
    if pd.isna(valor):
        return ""

    texto = str(valor)

    # remove quebras de linha
    texto = texto.replace("\n", " ").replace("\r", " ")

    # remove múltiplos espaços
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def limpar_numeros(valor):
    """
    Limpa números:
    - remove textos
    - mantém apenas números e ponto
    """
    if pd.isna(valor):
        return 0

    valor = str(valor)

    valor = re.sub(r"[^\d.,]", "", valor)

    # troca vírgula por ponto
    valor = valor.replace(",", ".")

    try:
        return float(valor)
    except:
        return 0


def limpar_dataframe_completo(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpeza EXTREMA:
    - remove colunas vazias
    - remove linhas vazias
    - limpa textos
    - limpa números automaticamente quando possível
    """
    df = df.copy()

    # remove vazios
    df = df.dropna(axis=1, how="all")
    df = df.dropna(axis=0, how="all")

    # normaliza colunas
    df.columns = [str(c).strip() for c in df.columns]

    for col in df.columns:
        # tenta identificar número
        if df[col].astype(str).str.contains(r"\d").mean() > 0.5:
            df[col] = df[col].apply(limpar_numeros)
        else:
            df[col] = df[col].apply(limpar_texto)

    return df


def padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Padroniza nomes de colunas para facilitar mapeamento:
    ex:
    "Nome do Produto" -> "nome_produto"
    """
    df = df.copy()

    novas_colunas = []
    for col in df.columns:
        col = col.lower().strip()
        col = re.sub(r"\s+", "_", col)
        col = re.sub(r"[^\w_]", "", col)
        novas_colunas.append(col)

    df.columns = novas_colunas
    return df


def remover_duplicados(df: pd.DataFrame, coluna: str = None) -> pd.DataFrame:
    """
    Remove duplicados:
    - se coluna informada: usa ela
    - senão: remove linhas iguais completas
    """
    if coluna and coluna in df.columns:
        return df.drop_duplicates(subset=[coluna])

    return df.drop_duplicates()
