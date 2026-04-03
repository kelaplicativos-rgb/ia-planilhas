import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="Bling App Zero", layout="wide")

st.title("Bling App Zero")
st.write("Base inicial do sistema")

BASE_DIR = Path(__file__).parent
PASTA_MODELOS = BASE_DIR / "bling_app_zero" / "modelos"

ARQUIVO_PRODUTOS = PASTA_MODELOS / "produtos.xlsx"
ARQUIVO_ESTOQUE = PASTA_MODELOS / "saldo_estoque.xlsx"


def ler_planilha(caminho):
    try:
        df = pd.read_excel(caminho)
        return df, None
    except Exception as e:
        return None, str(e)


def limpar_planilha(df):
    df = df.copy()

    # remove linhas totalmente vazias
    df = df.dropna(how="all")

    # remove espaços extras
    df = df.applymap(lambda x: str(x).strip() if pd.notnull(x) else x)

    # substitui string "None" por vazio
    df = df.replace("None", "")

    return df


st.subheader("Verificação dos modelos")

if ARQUIVO_PRODUTOS.exists():
    df_produtos, erro_produtos = ler_planilha(ARQUIVO_PRODUTOS)

    if df_produtos is not None:
        df_produtos = limpar_planilha(df_produtos)

    if erro_produtos:
        st.error(f"Erro ao ler produtos.xlsx: {erro_produtos}")
    else:
        st.success("produtos.xlsx carregado com sucesso")
        st.write(f"Linhas: {len(df_produtos)} | Colunas: {len(df_produtos.columns)}")
        st.dataframe(df_produtos.head())
else:
    st.warning("Arquivo produtos.xlsx não encontrado na pasta bling_app_zero/modelos")


if ARQUIVO_ESTOQUE.exists():
    df_estoque, erro_estoque = ler_planilha(ARQUIVO_ESTOQUE)

    if df_estoque is not None:
        df_estoque = limpar_planilha(df_estoque)

    if erro_estoque:
        st.error(f"Erro ao ler saldo_estoque.xlsx: {erro_estoque}")
    else:
        st.success("saldo_estoque.xlsx carregado com sucesso")
        st.write(f"Linhas: {len(df_estoque)} | Colunas: {len(df_estoque.columns)}")
        st.dataframe(df_estoque.head())
else:
    st.warning("Arquivo saldo_estoque.xlsx não encontrado na pasta bling_app_zero/modelos")


st.subheader("Depósito manual")
deposito_manual = st.text_input("Digite o nome do depósito")

if deposito_manual:
    st.info(f"Depósito informado: {deposito_manual}")
