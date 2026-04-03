from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Union

import pandas as pd


ArquivoLike = Union[str, Path, BytesIO]


# =========================
# LEITURA
# =========================
def ler_excel(arquivo: ArquivoLike) -> pd.DataFrame:
    """
    Lê Excel (.xlsx)
    """
    df = pd.read_excel(arquivo, dtype=object)
    return normalizar_colunas(df)


def ler_csv(arquivo: ArquivoLike) -> pd.DataFrame:
    """
    Lê CSV com tentativa inteligente (Brasil)
    """
    tentativas = [
        {"sep": ";", "encoding": "utf-8"},
        {"sep": ";", "encoding": "latin-1"},
        {"sep": ",", "encoding": "utf-8"},
        {"sep": ",", "encoding": "latin-1"},
    ]

    for cfg in tentativas:
        try:
            df = pd.read_csv(
                arquivo,
                sep=cfg["sep"],
                encoding=cfg["encoding"],
                dtype=object,
            )
            return normalizar_colunas(df)
        except Exception:
            continue

    raise ValueError("Não foi possível ler o CSV.")


def ler_planilha(arquivo: ArquivoLike) -> pd.DataFrame:
    """
    Detecta automaticamente CSV ou Excel
    """
    if hasattr(arquivo, "name"):
        nome = arquivo.name.lower()
    else:
        nome = str(arquivo).lower()

    if nome.endswith(".xlsx"):
        return ler_excel(arquivo)

    if nome.endswith(".csv"):
        return ler_csv(arquivo)

    raise ValueError("Formato não suportado. Use .xlsx ou .csv")


# =========================
# LIMPEZA
# =========================
def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """
    Padroniza nomes das colunas
    """
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def limpar_valores_vazios(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpeza pesada:
    - remove NaN
    - remove espaços
    - transforma tudo em string segura
    """
    df = df.copy()

    df = df.fillna("")

    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()

    return df


def limpar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpeza estrutural:
    - remove linhas/colunas vazias
    """
    df = df.copy()

    df = df.dropna(axis=0, how="all")
    df = df.dropna(axis=1, how="all")

    return df


# =========================
# EXPORTAÇÃO
# =========================
def salvar_excel_bytes(df: pd.DataFrame, nome_aba: str = "Planilha") -> BytesIO:
    """
    Gera Excel em memória (download Streamlit)
    """
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=nome_aba)

    output.seek(0)
    return output


def salvar_csv_bytes(df: pd.DataFrame) -> BytesIO:
    """
    Gera CSV em memória
    """
    output = BytesIO()
    csv_str = df.to_csv(index=False, sep=";", encoding="utf-8-sig")
    output.write(csv_str.encode("utf-8-sig"))
    output.seek(0)
    return output
