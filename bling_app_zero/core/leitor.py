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

    if df is None or df.empty:
        return None

    return df


def validar_planilha_vazia(df):
    if df is None:
        return False

    if not isinstance(df, pd.DataFrame):
        return False

    return not df.empty


def validar_planilha_basica(df):
    return validar_planilha_vazia(df)


def preview(df):
    if df is None or df.empty:
        st.warning("⚠️ Nenhuma planilha carregada.")
        return pd.DataFrame()

    if bloco_toggle("Preview", "preview"):
        prev = gerar_preview(df, 1)
        st.dataframe(prev, use_container_width=True)
        return prev

    return pd.DataFrame()


def mostrar_colunas(df):
    if df is None or df.empty:
        return

    if bloco_toggle("Colunas identificadas automaticamente", "colunas_auto"):
        st.write(list(df.columns))


def ajuste_manual(df):
    if df is None or df.empty:
        return {}

    if bloco_toggle("Ajuste manual das colunas", "ajuste_manual"):
        st.info("🛠️ Ajuste manual será conectado no próximo módulo.")

    return {}


def mostrar_mapeamento(mapeamento):
    if not mapeamento:
        return

    if bloco_toggle("Mapeamento final que será usado", "map_final"):
        st.json(mapeamento)
