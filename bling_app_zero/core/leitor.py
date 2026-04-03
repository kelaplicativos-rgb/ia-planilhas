# bling_app_zero/core/leitor.py

import pandas as pd
import streamlit as st

from ..utils.excel import (
    ler_planilha,
    limpar_valores_vazios,
    normalizar_colunas,
    gerar_preview,
    bloco_toggle,
)


# =========================================================
# CARREGAR PLANILHA
# =========================================================
def carregar_planilha(arquivo):
    if arquivo is None:
        return None

    df = ler_planilha(arquivo)

    if df is None or df.empty:
        return None

    df = normalizar_colunas(df)
    df = limpar_valores_vazios(df)

    return df


# =========================================================
# VALIDAR PLANILHA
# =========================================================
def validar_planilha_vazia(df):
    if df is None:
        return False

    if isinstance(df, pd.DataFrame):
        return not df.empty

    return False


# =========================================================
# PREVIEW (1 LINHA)
# =========================================================
def preview(df):
    if df is None or df.empty:
        st.warning("⚠️ Nenhuma planilha carregada.")
        return

    if bloco_toggle("Preview", "preview"):
        st.dataframe(gerar_preview(df, 1), use_container_width=True)


# =========================================================
# COLUNAS IDENTIFICADAS
# =========================================================
def mostrar_colunas(df):
    if df is None or df.empty:
        return

    if bloco_toggle("Colunas identificadas automaticamente", "colunas_auto"):
        st.write(list(df.columns))


# =========================================================
# AJUSTE MANUAL (placeholder)
# =========================================================
def ajuste_manual(df):
    if df is None or df.empty:
        return

    if bloco_toggle("Ajuste manual das colunas", "ajuste_manual"):
        st.info("🛠️ Em breve ajuste manual inteligente aqui")


# =========================================================
# MAPEAMENTO FINAL
# =========================================================
def mostrar_mapeamento(mapeamento):
    if not mapeamento:
        return

    if bloco_toggle("Mapeamento final que será usado", "map_final"):
        st.json(mapeamento)
