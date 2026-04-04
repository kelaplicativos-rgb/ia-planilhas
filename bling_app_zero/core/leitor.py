import pandas as pd
import streamlit as st

from ..utils.excel import (
    ler_planilha,
    limpar_valores_vazios,
    normalizar_colunas,
    gerar_preview,
    bloco_toggle,
)
from ..utils.xml_nfe import ler_xml_nfe, arquivo_parece_xml_nfe


def carregar_planilha(arquivo):
    """
    Lê, normaliza e limpa a entrada enviada.
    Aceita:
    - Excel / CSV
    - XML de NF-e

    Retorna um DataFrame pronto para uso ou None em caso de falha.
    """
    if arquivo is None:
        return None

    try:
        if arquivo_parece_xml_nfe(arquivo):
            df = ler_xml_nfe(arquivo)
        else:
            df = ler_planilha(arquivo)
    except Exception as e:
        st.error(f"Erro ao ler o arquivo: {e}")
        return None

    if df is None or df.empty:
        return None

    try:
        df = normalizar_colunas(df)
        df = limpar_valores_vazios(df)
    except Exception as e:
        st.error(f"Erro ao preparar os dados: {e}")
        return None

    if df is None or df.empty:
        return None

    return df


def validar_planilha_basica(df):
    """
    Validação mínima para garantir que a planilha/arquivo existe
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


def mostrar_preview_planilha(df, linhas=1, titulo="Preview"):
    """
    Exibe preview controlado do DataFrame.
    """
    if not validar_planilha_basica(df):
        st.warning("Nenhum dado válido para mostrar no preview.")
        return

    if bloco_toggle(titulo, f"toggle_{titulo.lower().replace(' ', '_')}"):
        st.dataframe(gerar_preview(df, linhas=linhas), use_container_width=True)


def obter_colunas(df):
    """
    Retorna lista de colunas do DataFrame.
    """
    if not validar_planilha_basica(df):
        return []

    return list(df.columns)


def dataframe_para_registros(df):
    """
    Converte DataFrame em lista de dicts.
    """
    if not validar_planilha_basica(df):
        return []

    return df.to_dict(orient="records")
