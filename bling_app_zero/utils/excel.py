from __future__ import annotations

import pandas as pd
import streamlit as st
from typing import Any


# ==========================================================
# LEITURA SEGURA DE PLANILHA (🔥 CORREÇÃO PRINCIPAL)
# ==========================================================
def ler_planilha_segura(arquivo: Any) -> pd.DataFrame:
    """
    Lê planilha de forma segura (xlsx, xls, csv, xlsb)
    Nunca quebra o sistema
    """

    if arquivo is None:
        return pd.DataFrame()

    try:
        nome = getattr(arquivo, "name", "").lower()

        # =========================
        # EXCEL
        # =========================
        if nome.endswith(".xlsx") or nome.endswith(".xls"):
            df = pd.read_excel(arquivo)

        # =========================
        # CSV
        # =========================
        elif nome.endswith(".csv"):
            df = pd.read_csv(arquivo, sep=None, engine="python")

        # =========================
        # XLSB
        # =========================
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
# SAFE DF (compatível com fluxo do sistema)
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
# 🔥 NOVO: LIMPAR DADOS MANTENDO CABEÇALHO
# ==========================================================
def limpar_dados_manter_cabecalho(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mantém apenas o cabeçalho (estrutura do modelo Bling)
    """
    try:
        return df.iloc[0:0].copy()
    except Exception:
        return pd.DataFrame(columns=df.columns if hasattr(df, "columns") else [])


# ==========================================================
# 🔥 NOVO: REAPROVEITAR MODELO PADRÃO
# ==========================================================
def reaproveitar_modelo(df_modelo: pd.DataFrame, df_dados: pd.DataFrame) -> pd.DataFrame:
    """
    Usa o modelo Bling como base e injeta os dados mapeados
    """

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
