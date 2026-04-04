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
    """
    Lê, normaliza e limpa a planilha enviada.
    Retorna um DataFrame pronto para uso ou None em caso de falha.
    """
    if arquivo is None:
        return None

    try:
        df = ler_planilha(arquivo)
    except Exception as e:
        st.error(f"Erro ao ler a planilha: {e}")
        return None

    if df is None or df.empty:
        return None

    try:
        df = normalizar_colunas(df)
        df = limpar_valores_vazios(df)
    except Exception as e:
        st.error(f"Erro ao preparar a planilha: {e}")
        return None

    if df is None or df.empty:
        return None

    return df


def validar_planilha_basica(df):
    """
    Validação mínima para garantir que a planilha existe
    e possui conteúdo utilizável.
    """
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
    """
    Exibe preview enxuto da planilha.
    Mantém o comportamento fechado por padrão via bloco_toggle.
    """
    if not validar_planilha_basica(df):
        return

    if bloco_toggle("Preview", "preview"):
        try:
            st.dataframe(gerar_preview(df, linhas), use_container_width=True)
        except Exception:
            st.dataframe(df.head(linhas), use_container_width=True)


def mostrar_colunas(df):
    """
    Exibe lista de colunas da planilha.
    Mantém o comportamento fechado por padrão via bloco_toggle.
    """
    if not validar_planilha_basica(df):
        return

    if bloco_toggle("Colunas", "cols"):
        st.write(list(df.columns))
