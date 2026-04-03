import streamlit as st
import pandas as pd
from pathlib import Path

st.set_page_config(page_title="🔥 Bling Automação PRO", layout="wide")

st.title("🔥 Bling Automação PRO")
st.subheader("🧠 Base limpa para padrão Bling")

# =========================
# CAMINHOS
# =========================
BASE_DIR = Path(__file__).parent
PASTA_MODELOS = BASE_DIR / "bling_app_zero" / "modelos"

ARQ_PROD = PASTA_MODELOS / "produtos.xlsx"
ARQ_EST = PASTA_MODELOS / "saldo_estoque.xlsx"

# =========================
# FUNÇÃO LEITURA
# =========================
def ler_excel(caminho):
    try:
        df = pd.read_excel(caminho)
        return df, None
    except Exception as e:
        return None, str(e)

# =========================
# LIMPEZA PROFISSIONAL
# =========================
def limpar_total(df):
    df = df.copy()

    # remove linhas totalmente vazias
    df = df.dropna(how="all")

    # remove espaços invisíveis
    df.columns = [str(c).strip() for c in df.columns]

    # limpa valores
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip()

    # remove "None"
    df = df.replace("None", "")

    # remove NaN
    df = df.fillna("")

    # REMOVE TODOS OS DADOS (mantém só estrutura)
    df = df.iloc[0:0]

    return df

# =========================
# INTERFACE
# =========================
st.header("📦 Verificação dos modelos")

# =========================
# PRODUTOS
# =========================
if ARQ_PROD.exists():
    prod, erro = ler_excel(ARQ_PROD)

    if prod is not None:
        st.success("✅ produtos.xlsx carregado")

        st.write("📊 Colunas detectadas:")
        st.write(list(prod.columns))

        prod_limpo = limpar_total(prod)

        st.write("🧼 Estrutura após limpeza:")
        st.dataframe(prod_limpo)

        st.info(f"Colunas: {len(prod_limpo.columns)} | Linhas: {len(prod_limpo)}")

    else:
        st.error(f"Erro: {erro}")
else:
    st.error("❌ produtos.xlsx não encontrado")

# =========================
# ESTOQUE
# =========================
if ARQ_EST.exists():
    est, erro = ler_excel(ARQ_EST)

    if est is not None:
        st.success("✅ saldo_estoque.xlsx carregado")

        st.write("📊 Colunas detectadas:")
        st.write(list(est.columns))

        est_limpo = limpar_total(est)

        st.write("🧼 Estrutura após limpeza:")
        st.dataframe(est_limpo)

        st.info(f"Colunas: {len(est_limpo.columns)} | Linhas: {len(est_limpo)}")

    else:
        st.error(f"Erro: {erro}")
else:
    st.error("❌ saldo_estoque.xlsx não encontrado")

# =========================
# DEPÓSITO (já preparando)
# =========================
st.header("🏬 Depósito manual")

deposito = st.text_input("Digite o nome do depósito (ex: Geral, Loja, CD)")

if deposito:
    st.success(f"Depósito definido: {deposito}")
