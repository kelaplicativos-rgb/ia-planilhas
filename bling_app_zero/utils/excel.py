from __future__ import annotations

import pandas as pd
import streamlit as st
from typing import Any
from io import BytesIO


# ==========================================================
# 🔥 LEITURA SEGURA (NOVO)
# ==========================================================
def ler_planilha_segura(arquivo: Any) -> pd.DataFrame:
    if arquivo is None:
        return pd.DataFrame()

    try:
        nome = getattr(arquivo, "name", "").lower()

        if nome.endswith(".xlsx") or nome.endswith(".xls"):
            df = pd.read_excel(arquivo)

        elif nome.endswith(".csv"):
            df = pd.read_csv(arquivo, sep=None, engine="python")

        elif nome.endswith(".xlsb"):
            df = pd.read_excel(arquivo, engine="pyxlsb")

        else:
            st.warning("Formato não suportado")
            return pd.DataFrame()

        return _normalizar_df(df)

    except Exception as e:
        st.error(f"Erro ao ler planilha: {e}")
        return pd.DataFrame()


# ==========================================================
# NORMALIZAÇÃO
# ==========================================================
def _normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df.columns = [str(col).strip() for col in df.columns]
        return df
    except Exception:
        return df


# ==========================================================
# SAFE DF
# ==========================================================
def safe_df_dados(df: Any) -> pd.DataFrame:
    try:
        if isinstance(df, pd.DataFrame):
            return df.copy()

        if df is None:
            return pd.DataFrame()

        return pd.DataFrame(df)

    except Exception:
        return pd.DataFrame()


# ==========================================================
# 🔥 EXPORTAÇÃO (OBRIGATÓRIO PRO SISTEMA)
# ==========================================================
def df_to_excel_bytes(df: pd.DataFrame) -> bytes:
    try:
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)
        return output.getvalue()
    except Exception:
        return b""


def exportar_dataframe_para_excel(df: pd.DataFrame, nome_arquivo: str = "planilha.xlsx"):
    try:
        excel_bytes = df_to_excel_bytes(df)

        st.download_button(
            label="📥 Baixar planilha",
            data=excel_bytes,
            file_name=nome_arquivo,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    except Exception as e:
        st.error(f"Erro ao exportar: {e}")


# ==========================================================
# 🔥 DOWNLOAD LOG (OBRIGATÓRIO)
# ==========================================================
def baixar_logs_txt(texto: str, nome: str = "log_processamento.txt"):
    try:
        st.download_button(
            label="📄 Baixar log",
            data=texto.encode("utf-8"),
            file_name=nome,
            mime="text/plain",
        )
    except Exception as e:
        st.error(f"Erro ao baixar log: {e}")


# ==========================================================
# 🔥 LIMPAR MODELO (SEU PEDIDO)
# ==========================================================
def limpar_dados_manter_cabecalho(df: pd.DataFrame) -> pd.DataFrame:
    try:
        return df.iloc[0:0].copy()
    except Exception:
        return pd.DataFrame(columns=df.columns if hasattr(df, "columns") else [])


# ==========================================================
# 🔥 REAPROVEITAR MODELO
# ==========================================================
def reaproveitar_modelo(df_modelo: pd.DataFrame, df_dados: pd.DataFrame) -> pd.DataFrame:
    try:
        if df_modelo is None or df_modelo.empty:
            return df_dados

        df_saida = limpar_dados_manter_cabecalho(df_modelo)

        for col in df_saida.columns:
            if col in df_dados.columns:
                df_saida[col] = df_dados[col]
            else:
                df_saida[col] = ""

        return df_saida

    except Exception as e:
        st.error(f"Erro ao reaproveitar modelo: {e}")
        return df_dados
