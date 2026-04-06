from __future__ import annotations

import hashlib
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st


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
# LEITOR UNIVERSAL
# ==========================================================
def ler_planilha_segura(arquivo):
    try:
        nome = arquivo.name.lower()

        if nome.endswith(".csv"):
            try:
                df = pd.read_csv(arquivo, encoding="utf-8")
            except Exception:
                df = pd.read_csv(arquivo, encoding="latin1")

        elif nome.endswith((".xlsx", ".xls", ".xlsm", ".xlsb")):
            df = pd.read_excel(arquivo)

        else:
            st.error("Formato não suportado")
            return None

        df = df.dropna(how="all")
        return df

    except Exception as e:
        log_debug(f"Erro leitura planilha: {e}", "ERROR")
        st.error("Erro ao ler arquivo")
        return None


# ==========================================================
# HELPERS
# ==========================================================
def hash_df(df: pd.DataFrame) -> str:
    return hashlib.md5(
        pd.util.hash_pandas_object(df, index=True).values.tobytes()
    ).hexdigest()


def exportar_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buffer.seek(0)
    return buffer.read()


def safe_preview(df: pd.DataFrame, rows: int = 20) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    return df.head(rows)
