from __future__ import annotations

import re
import unicodedata
import pandas as pd


def remover_acentos(texto: str) -> str:
    """
    Remove acentos e normaliza caracteres Unicode.
    """
    if texto is None:
        return ""

    texto = str(texto)
    texto = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def limpar_texto(valor) -> str:
    """
    Limpeza segura de texto:
    - trata nulos
    - remove quebras de linha
    - remove tabs
    - remove espaços duplicados
    - remove caracteres invisíveis comuns
    """
    if valor is None:
        return ""

    try:
        if pd.isna(valor):
            return ""
    except Exception:
        pass

    texto = str(valor)

    texto = texto.replace("\ufeff", " ")
    texto = texto.replace("\u200b", " ")
    texto = texto.replace("\xa0", " ")
    texto = texto.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()


def limpar_numeros(valor, default=0):
    """
    Limpa números sem quebrar formato decimal brasileiro:
    - remove textos e símbolos
    - suporta vírgula e ponto
    - retorna float
    """
    if valor is None:
        return default

    try:
        if pd.isna(valor):
            return default
    except Exception:
        pass

    valor = str(valor).strip()

    if valor == "":
        return default

    valor = re.sub(r"[^\d,.\-]", "", valor)

    if "," in valor and "." in valor:
        if valor.rfind(",") > valor.rfind("."):
            valor = valor.replace(".", "")
            valor = valor.replace(",", ".")
        else:
            valor = valor.replace(",", "")
    elif "," in valor:
        valor = valor.replace(".", "")
        valor = valor.replace(",", ".")

    if valor in {"", "-", ".", "-.", ".-", "--"}:
        return default

    try:
        return float(valor)
    except Exception:
        return default


def slug_coluna(coluna: str) -> str:
    """
    Padroniza nome de coluna para facilitar mapeamento:
    ex:
    'Nome do Produto' -> 'nome_do_produto'
    """
    coluna = limpar_texto(coluna)
    coluna = remover_acentos(coluna).lower()
    coluna = coluna.replace("/", " ")
    coluna = coluna.replace("\\", " ")
    coluna = coluna.replace("-", " ")
    coluna = re.sub(r"[^a-z0-9 ]+", "", coluna)
    coluna = re.sub(r"\s+", "_", coluna).strip("_")

    if not coluna:
        coluna = "coluna"

    return coluna


def padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Padroniza nomes de colunas e evita duplicidade:
    ex:
    'Nome do Produto' -> 'nome_do_produto'
    """
    df = df.copy()

    novas_colunas = []
    usados = {}

    for col in df.columns:
        base = slug_coluna(col)

        if base not in usados:
            usados[base] = 1
            novas_colunas.append(base)
        else:
            usados[base] += 1
            novas_colunas.append(f"{base}_{usados[base]}")

    df.columns = novas_colunas
    return df


def limpar_series_texto(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpa todas as células como texto de forma segura.
    Não tenta adivinhar número automaticamente para não
    corromper SKU, GTIN, códigos e descrições.
    """
    df = df.copy()

    for col in df.columns:
        df[col] = df[col].apply(limpar_texto)

    return df


def limpar_dataframe_completo(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpeza completa e segura para planilhas de fornecedores:
    - remove linhas/colunas totalmente vazias
    - padroniza nomes de colunas
    - limpa todos os valores como texto
    - remove espaços extras
    - reseta índice
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    df.columns = [limpar_texto(c) for c in df.columns]

    df = df.dropna(axis=1, how="all")
    df = df.dropna(axis=0, how="all")

    df = padronizar_colunas(df)
    df = limpar_series_texto(df)

    df = df.replace("", pd.NA)
    df = df.dropna(axis=1, how="all")
    df = df.dropna(axis=0, how="all")
    df = df.fillna("")

    df = df.reset_index(drop=True)

    return df


def remover_duplicados(df: pd.DataFrame, coluna: str | None = None) -> pd.DataFrame:
    """
    Remove duplicados:
    - se coluna informada e existir: usa ela
    - senão: remove linhas idênticas
    """
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df.copy()

    df = df.copy()

    if coluna:
        coluna = limpar_texto(coluna)
        if coluna in df.columns:
            return df.drop_duplicates(subset=[coluna], keep="first").reset_index(drop=True)

    return df.drop_duplicates(keep="first").reset_index(drop=True)


def limpar_coluna_numerica(df: pd.DataFrame, coluna: str, default=0) -> pd.DataFrame:
    """
    Limpa uma coluna específica como numérica.
    Use apenas quando souber que a coluna deve ser número.
    """
    if df is None or df.empty:
        return pd.DataFrame() if df is None else df.copy()

    df = df.copy()

    if coluna in df.columns:
        df[coluna] = df[coluna].apply(lambda x: limpar_numeros(x, default=default))

    return df
