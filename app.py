import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="Bling App PRO", layout="wide")

st.title("🔥 Bling Automação PRO")

BASE_DIR = Path(__file__).parent
PASTA_MODELOS = BASE_DIR / "bling_app_zero" / "modelos"

ARQ_PROD = PASTA_MODELOS / "produtos.xlsx"
ARQ_EST = PASTA_MODELOS / "saldo_estoque.xlsx"


def ler_planilha(caminho):
    try:
        return pd.read_excel(caminho), None
    except Exception as e:
        return None, str(e)


def limpar(df):
    df = df.copy()
    df = df.dropna(how="all")
    df = df.applymap(lambda x: str(x).strip() if pd.notnull(x) else x)
    df = df.replace("None", "")
    return df


def mapear(df):
    novo = pd.DataFrame()

    novo["codigo"] = df.get("Código", "")
    novo["descricao"] = df.get("Descrição", "")
    novo["unidade"] = df.get("Unidade", "UN")
    novo["preco"] = df.get("Preço", 0)
    novo["situacao"] = df.get("Situação", "Ativo")

    return novo


def juntar(prod, est):
    if "Código" in prod.columns and "Código" in est.columns:
        df = pd.merge(prod, est, on="Código", how="left")
    else:
        df = prod.copy()

    # tenta puxar estoque
    if "Estoque" in df.columns:
        df["estoque"] = df["Estoque"]
    else:
        df["estoque"] = 0

    return df


st.subheader("📦 Processamento completo")

if ARQ_PROD.exists():
    prod, erro = ler_planilha(ARQ_PROD)

    if prod is not None:
        prod = limpar(prod)

        st.success("Produtos OK")

        if ARQ_EST.exists():
            est, erro2 = ler_planilha(ARQ_EST)

            if est is not None:
                est = limpar(est)
                st.success("Estoque OK")

                final = juntar(prod, est)

            else:
                st.warning("Erro estoque")
                final = prod

        else:
            st.warning("Sem estoque")
            final = prod

        bling = mapear(final)

        # adiciona estoque final
        bling["estoque"] = final.get("estoque", 0)

        st.subheader("📊 Resultado final")
        st.dataframe(bling.head())

        csv = bling.to_csv(index=False).encode("utf-8")

        st.download_button(
            "⬇️ Baixar Bling COMPLETO",
            csv,
            "bling_final.csv",
            "text/csv"
        )

    else:
        st.error(erro)
else:
    st.error("produtos.xlsx não encontrado")
