import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="Bling App Zero", layout="wide")

st.title("🔥 Bling App Zero")
st.write("Sistema inteligente de planilhas")

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
    df = df.dropna(how="all")
    df = df.applymap(lambda x: str(x).strip() if pd.notnull(x) else x)
    df = df.replace("None", "")
    return df


def mapear_para_bling(df):
    novo = pd.DataFrame()

    novo["codigo"] = df.get("Código", "")
    novo["descricao"] = df.get("Descrição", "")
    novo["unidade"] = df.get("Unidade", "UN")
    novo["preco"] = df.get("Preço", 0)
    novo["situacao"] = df.get("Situação", "Ativo")

    novo["marca"] = df.get("Marca", "")
    novo["ncm"] = df.get("NCM", "")
    novo["observacoes"] = df.get("Observações", "")

    return novo


st.subheader("📦 Produtos")

if ARQUIVO_PRODUTOS.exists():
    df_produtos, erro = ler_planilha(ARQUIVO_PRODUTOS)

    if df_produtos is not None:
        df_produtos = limpar_planilha(df_produtos)

        st.success("Planilha carregada")
        st.dataframe(df_produtos.head())

        st.subheader("🔄 Convertido para Bling")

        df_bling = mapear_para_bling(df_produtos)

        st.dataframe(df_bling.head())

        csv = df_bling.to_csv(index=False).encode("utf-8")

        st.download_button(
            "⬇️ Baixar CSV para Bling",
            csv,
            "bling_produtos.csv",
            "text/csv"
        )

    else:
        st.error(erro)
else:
    st.warning("Arquivo produtos.xlsx não encontrado")


st.subheader("🏢 Depósito")

deposito = st.text_input("Nome do depósito")

if deposito:
    st.success(f"Depósito definido: {deposito}")
