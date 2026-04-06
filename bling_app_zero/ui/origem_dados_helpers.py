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
# 🔥 LEITOR UNIVERSAL (ULTRA ROBUSTO)
# ==========================================================
def ler_planilha_segura(arquivo):
    try:
        nome = arquivo.name.lower()
        log_debug(f"Lendo arquivo: {nome}")

        # =========================
        # CSV
        # =========================
        if nome.endswith(".csv"):

            try:
                df = pd.read_csv(arquivo, encoding="utf-8")
            except Exception:
                try:
                    df = pd.read_csv(arquivo, encoding="latin1")
                except Exception:
                    df = pd.read_csv(arquivo, sep=";", encoding="latin1")

        # =========================
        # EXCEL
        # =========================
        elif nome.endswith((".xlsx", ".xls", ".xlsm", ".xlsb")):
            df = pd.read_excel(arquivo)

        else:
            log_debug("Formato não suportado", "ERROR")
            st.error("Formato não suportado")
            return None

        # =========================
        # LIMPEZA
        # =========================
        df = df.dropna(how="all")

        if df.empty:
            log_debug("Arquivo carregado mas vazio", "WARNING")
        else:
            log_debug(f"Arquivo carregado: {df.shape}", "SUCCESS")

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
    try:
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)

        buffer.seek(0)
        log_debug("Excel exportado com sucesso", "SUCCESS")
        return buffer.read()

    except Exception as e:
        log_debug(f"Erro exportar excel: {e}", "ERROR")
        st.error("Erro ao gerar Excel")
        return b""


def safe_preview(df: pd.DataFrame, rows: int = 20) -> pd.DataFrame:
    try:
        if df is None or df.empty:
            return pd.DataFrame()
        return df.head(rows)
    except Exception as e:
        log_debug(f"Erro preview: {e}", "ERROR")
        return pd.DataFrame()
