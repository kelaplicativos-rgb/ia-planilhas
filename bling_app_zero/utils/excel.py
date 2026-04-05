from __future__ import annotations

from io import BytesIO
import csv

import pandas as pd
import streamlit as st


ENCODINGS_CSV = ("utf-8", "utf-8-sig", "latin1", "cp1252")
SEPARADORES_CSV = (",", ";", "\t", "|")


def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(col).strip() for col in df.columns]
    return df


def limpar_valores_vazios(df: pd.DataFrame) -> pd.DataFrame:
    if df is None:
        return pd.DataFrame()
    df = df.copy()
    df = df.replace({pd.NA: "", "nan": "", "NaN": "", "None": ""})
    return df.fillna("")


def _ler_csv_bytes(conteudo: bytes) -> pd.DataFrame:
    ultimo_erro: Exception | None = None

    for encoding in ENCODINGS_CSV:
        try:
            texto = conteudo.decode(encoding)
        except Exception as e:
            ultimo_erro = e
            continue

        try:
            amostra = texto[:4096]
            try:
                dialect = csv.Sniffer().sniff(amostra, delimiters=";,\t|")
                candidatos = [dialect.delimiter] + [s for s in SEPARADORES_CSV if s != dialect.delimiter]
            except Exception:
                candidatos = list(SEPARADORES_CSV)

            for sep in candidatos:
                try:
                    df = pd.read_csv(BytesIO(conteudo), sep=sep, encoding=encoding, dtype=str)
                    if df is not None and len(df.columns) > 0:
                        return df
                except Exception as e:
                    ultimo_erro = e
                    continue
        except Exception as e:
            ultimo_erro = e
            continue

    if ultimo_erro is not None:
        raise ultimo_erro
    raise ValueError("Não foi possível ler o CSV informado.")


def ler_planilha(arquivo) -> pd.DataFrame:
    if arquivo is None:
        return pd.DataFrame()

    nome = str(getattr(arquivo, "name", "")).lower().strip()

    if hasattr(arquivo, "seek"):
        arquivo.seek(0)
    conteudo = arquivo.read()
    if hasattr(arquivo, "seek"):
        arquivo.seek(0)

    if not conteudo:
        return pd.DataFrame()

    if nome.endswith(".csv"):
        df = _ler_csv_bytes(conteudo)
    elif nome.endswith((".xlsx", ".xls")):
        df = pd.read_excel(BytesIO(conteudo), dtype=str)
    else:
        try:
            df = pd.read_excel(BytesIO(conteudo), dtype=str)
        except Exception:
            df = _ler_csv_bytes(conteudo)

    df = normalizar_colunas(df)
    df = limpar_valores_vazios(df)
    return df


def gerar_preview(df: pd.DataFrame, linhas: int = 5) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    linhas = max(1, int(linhas or 1))
    return df.head(linhas).copy()


def bloco_toggle(label: str, key: str) -> bool:
    return st.checkbox(label, value=False, key=f"toggle_{key}")


def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    """
    Converte DataFrame para Excel (xlsx)
    """

    df = df.copy()

    colunas_padrao = {
        "preco": 0.0,
        "preco_custo": 0.0,
        "estoque": 0,
        "peso": 0.0,
    }

    for col, default in colunas_padrao.items():
        if col not in df.columns:
            df[col] = default

    if "custo_fornecedor" in df.columns:
        df["preco_custo"] = df["custo_fornecedor"]
    elif "preco_compra" in df.columns:
        df["preco_custo"] = df["preco_compra"]

    df["preco_custo"] = pd.to_numeric(df["preco_custo"], errors="coerce").fillna(0.0)

    if "gtin" in df.columns:
        def limpar_gtin(valor) -> str:
            valor = "" if valor is None else str(valor).strip()
            if not valor.isdigit():
                return ""
            if len(valor) not in [8, 12, 13, 14]:
                return ""
            return valor

        df["gtin"] = df["gtin"].apply(limpar_gtin)

    df["preco"] = pd.to_numeric(df["preco"], errors="coerce").fillna(0.0)
    df["preco_custo"] = pd.to_numeric(df["preco_custo"], errors="coerce").fillna(0.0)
    df["estoque"] = pd.to_numeric(df["estoque"], errors="coerce").fillna(0)
    df["peso"] = pd.to_numeric(df["peso"], errors="coerce").fillna(0.0)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)

    return output.getvalue()
