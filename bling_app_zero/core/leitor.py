import pandas as pd
import streamlit as st

from .roteador_entrada import carregar_entrada_upload
from ..utils.excel import gerar_preview, bloco_toggle


def carregar_planilha(arquivo):
    if arquivo is None:
        return None

    try:
        df = carregar_entrada_upload(arquivo)
    except Exception as e:
        st.error(f"Erro ao ler a entrada: {e}")
        return None

    if df is None or df.empty:
        return None

    return df


def validar_planilha_basica(df):
    if df is None:
        return False
    if not isinstance(df, pd.DataFrame):
        return False
    if df.empty:
        return False
    if len(df.columns) == 0:
        return False
    return True


def preview(df, linhas=1):
    if not validar_planilha_basica(df):
        return

    if bloco_toggle("Preview", "preview"):
        try:
            st.dataframe(gerar_preview(df, linhas), use_container_width=True)
        except Exception:
            st.dataframe(df.head(linhas), use_container_width=True)


def mostrar_colunas(df):
    if not validar_planilha_basica(df):
        return

    if bloco_toggle("Colunas", "cols"):
        st.write(list(df.columns))
