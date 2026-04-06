from __future__ import annotations

import hashlib
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st

from bling_app_zero.core.mapeamento_auto import sugestao_automatica


# ==========================================================
# LOG
# ==========================================================
def log_debug(msg: str, nivel: str = "INFO") -> None:
    try:
        if "logs" not in st.session_state:
            st.session_state["logs"] = []

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        linha = f"[{timestamp}] [{nivel}] {msg}"
        st.session_state["logs"].append(linha)
    except Exception:
        pass


# ==========================================================
# HELPERS
# ==========================================================
def _hash_df(df: pd.DataFrame) -> str:
    return hashlib.md5(
        pd.util.hash_pandas_object(df, index=True).values.tobytes()
    ).hexdigest()


def _exportar_df_exato_para_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buffer.seek(0)
    return buffer.read()


def _safe_preview(df: pd.DataFrame, rows: int = 20) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    return df.head(rows)


# ==========================================================
# GTIN
# ==========================================================
def _normalizar_gtin(valor) -> str:
    if pd.isna(valor):
        return ""

    texto = str(valor).strip()

    if texto.endswith(".0"):
        texto = texto[:-2]

    texto = "".join(ch for ch in texto if ch.isdigit())

    if len(texto) in (8, 12, 13, 14):
        return texto

    return ""


def _limpar_gtin(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    for col in df.columns:
        nome_col = str(col).lower()
        if "gtin" in nome_col or "ean" in nome_col:
            df[col] = df[col].apply(_normalizar_gtin)
    return df


# ==========================================================
# LEITURA ROBUSTA DE ARQUIVOS
# ==========================================================
def _limpar_nomes_colunas(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df

    novas = []
    usados = {}

    for col in df.columns:
        nome = str(col).strip()

        if nome == "" or nome.lower() == "nan":
            nome = "SEM_NOME"

        base = nome
        contador = usados.get(base, 0)

        if contador > 0:
            nome = f"{base}_{contador}"

        usados[base] = contador + 1
        novas.append(nome)
