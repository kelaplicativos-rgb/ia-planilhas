import pandas as pd
import streamlit as st

from ..utils.excel import (
    ler_planilha,
    limpar_valores_vazios,
    normalizar_colunas,
    gerar_preview,
    bloco_toggle,
)


def carregar_planilha(arquivo):
    if arquivo is None:
        return None

    df = ler_planilha(arquivo)

    if df is None or df.empty:
        return None

    df = normalizar_colunas(df)
    df = limpar_valores_vazios(df)

    return df


def validar_planilha_basica(df):
    if df is None:
        return False
    return not df.empty


def preview(df):
    if df is None:
        return

    if bloco_toggle("Preview", "preview"):
        st.dataframe(gerar_preview(df, 1))


def mostrar_colunas(df):
    if df is None:
        return

    if bloco_toggle("Colunas", "cols"):
        st.write(list(df.columns))
