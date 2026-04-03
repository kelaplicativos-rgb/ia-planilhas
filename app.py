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
    df = df.fillna("")
    return df


def numero(valor, padrao=0):
    try:
        texto = str(valor).strip().replace(".", "").replace(",", ".")
        if texto == "":
            return padrao
        return float(texto)
    except Exception:
        return padrao


def texto(valor, padrao=""):
    if pd.isna(valor):
        return padrao
    valor = str(valor).strip()
    if valor.lower() == "none":
        return padrao
    return valor


def juntar(prod, est):
    prod = prod.copy()
    est = est.copy()

    col_prod = "Código" if "Código" in prod.columns else None
    col_est = "Código produto *" if "Código produto *" in est.columns else None

    if col_prod and col_est:
        df = pd.merge(
            prod,
            est,
            left_on=col_prod,
            right_on=col_est,
            how="left"
        )
    else:
        df = prod.copy()

    if "Estoque" in df.columns:
        df["estoque_final"] = df["Estoque"]
    elif "Balanço (OBRIGATÓRIO)" in df.columns:
        df["estoque_final"] = df["Balanço (OBRIGATÓRIO)"]
    else:
        df["estoque_final"] = 0

    return df


def montar_planilha_bling(df):
    saida = pd.DataFrame()

    saida["Código"] = df["Código"].apply(texto) if "Código" in df.columns else ""
    saida["Descrição"] = df["Descrição"].apply(texto) if "Descrição" in df.columns else ""
    saida["Unidade"] = df["Unidade"].apply(lambda x: texto(x, "UN")) if "Unidade" in df.columns else "UN"
    saida["NCM"] = df["NCM"].apply(texto) if "NCM" in df.columns else ""
    saida["Origem"] = df["Origem"].apply(texto) if "Origem" in df.columns else ""
    saida["Preço"] = df["Preço"].apply(numero) if "Preço" in df.columns else 0
    saida["Valor IPI fixo"] = df["Valor IPI fixo"].apply(numero) if "Valor IPI fixo" in df.columns else 0
    saida["Observações"] = df["Observações"].apply(texto) if "Observações" in df.columns else ""
    saida["Situação"] = df["Situação"].apply(lambda x: texto(x, "Ativo")) if "Situação" in df.columns else "Ativo"
    saida["Estoque"] = df["estoque_final"].apply(numero) if "estoque_final" in df.columns else 0
    saida["Preço de custo"] = df["Preço de custo"].apply(numero) if "Preço de custo" in df.columns else 0
    saida["Cód no fornecedor"] = df["Cód no fornecedor"].apply(texto) if "Cód no fornecedor" in df.columns else ""
    saida["Fornecedor"] = df["Fornecedor"].apply(texto) if "Fornecedor" in df.columns else ""
    saida["Localização"] = df["Localização"].apply(texto) if "Localização" in df.columns else ""
    saida["Estoque máximo"] = df["Estoque máximo"].apply(numero) if "Estoque máximo" in df.columns else 0
    saida["Estoque mínimo"] = df["Estoque mínimo"].apply(numero) if "Estoque mínimo" in df.columns else 0

    return saida


st.subheader("📦 Processamento completo")

if ARQ_PROD.exists():
    prod, erro_prod = ler_planilha(ARQ_PROD)

    if prod is not None:
        prod = limpar(prod)
        st.success("Produtos OK")

        if ARQ_EST.exists():
            est, erro_est = ler_planilha(ARQ_EST)

            if est is not None:
                est = limpar(est)
                st.success("Estoque OK")
                final = juntar(prod, est)
            else:
                st.error(f"Erro ao ler estoque: {erro_est}")
                final = prod.copy()
        else:
            st.warning("Arquivo de estoque não encontrado")
            final = prod.copy()

        bling_final = montar_planilha_bling(final)

        st.subheader("📊 Resultado final")
        st.dataframe(bling_final.head())

        csv = bling_final.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            "⬇️ Baixar Bling COMPLETO",
            csv,
            "bling_final.csv",
            "text/csv"
        )

    else:
        st.error(f"Erro ao ler produtos: {erro_prod}")
else:
    st.error("produtos.xlsx não encontrado")
