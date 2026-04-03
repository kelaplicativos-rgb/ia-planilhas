import streamlit as st
import pandas as pd
import zipfile
import io
import os
from datetime import datetime

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="📦 Modo Final + Limpeza Inteligente", layout="wide")
st.title("📦 Upload + Limpeza Automática + ZIP Final")

# =========================
# SESSION STATE
# =========================
for key in ["df_estoque", "df_cadastro", "logs"]:
    if key not in st.session_state:
        st.session_state[key] = None if "df" in key else []

# =========================
# LOG
# =========================
def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    st.session_state["logs"].append(f"[{t}] {msg}")

# =========================
# LIMPEZA INTELIGENTE
# =========================
def limpar_dataframe(df):
    if df is None:
        return df

    # remover linhas totalmente vazias
    df = df.dropna(how="all")

    # remover colunas totalmente vazias
    df = df.dropna(axis=1, how="all")

    # limpar nomes de colunas
    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace("__", "_")
    )

    # limpar textos
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = (
                df[col]
                .astype(str)
                .str.strip()
                .str.replace("\n", " ")
                .str.replace("\r", " ")
            )

    # remover duplicados
    df = df.drop_duplicates()

    return df

# =========================
# LEITURA
# =========================
def ler_arquivo(nome, bytes_data):
    ext = os.path.splitext(nome.lower())[1]

    if ext == ".csv":
        try:
            df = pd.read_csv(io.BytesIO(bytes_data), sep=None, engine="python", encoding="utf-8")
        except:
            df = pd.read_csv(io.BytesIO(bytes_data), sep=None, engine="python", encoding="latin-1")
    else:
        df = pd.read_excel(io.BytesIO(bytes_data))

    return limpar_dataframe(df)

# =========================
# IDENTIFICAÇÃO
# =========================
def tipo_planilha(nome, df):
    nome = nome.lower()
    cols = " ".join(df.columns)

    if "estoque" in nome or "quantidade" in cols:
        return "estoque"

    if "cadastro" in nome or "descricao" in cols or "nome" in cols:
        return "cadastro"

    return None

# =========================
# EXTRAIR ZIP
# =========================
def processar_zip(zip_file):
    estoque = None
    cadastro = None

    with zipfile.ZipFile(zip_file) as z:
        arquivos = z.namelist()

        for nome in arquivos:
            if not nome.endswith((".xlsx", ".csv", ".xls")):
                continue

            dados = z.read(nome)
            df = ler_arquivo(nome, dados)

            tipo = tipo_planilha(nome, df)

            log(f"{nome} identificado como {tipo}")

            if tipo == "estoque" and estoque is None:
                estoque = df

            elif tipo == "cadastro" and cadastro is None:
                cadastro = df

    return estoque, cadastro

# =========================
# ZIP FINAL
# =========================
def gerar_zip(df1, df2):
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w") as z:
        if df1 is not None:
            z.writestr("estoque.xlsx", df1.to_excel(index=False, engine="openpyxl"))

        if df2 is not None:
            z.writestr("cadastro.xlsx", df2.to_excel(index=False, engine="openpyxl"))

        log_txt = "\n".join(st.session_state["logs"])
        z.writestr("log.txt", log_txt)

    buffer.seek(0)
    return buffer

# =========================
# UPLOAD
# =========================
modo = st.radio("Modo:", ["ZIP", "Arquivos soltos"], horizontal=True)

if modo == "ZIP":
    zip_file = st.file_uploader("Envie ZIP", type=["zip"])

    if zip_file:
        st.session_state["logs"] = []
        estoque, cadastro = processar_zip(zip_file)

        st.session_state["df_estoque"] = estoque
        st.session_state["df_cadastro"] = cadastro

else:
    arquivos = st.file_uploader("Envie arquivos", accept_multiple_files=True)

    if arquivos:
        st.session_state["logs"] = []

        for arq in arquivos:
            df = ler_arquivo(arq.name, arq.read())
            tipo = tipo_planilha(arq.name, df)

            log(f"{arq.name} identificado como {tipo}")

            if tipo == "estoque":
                st.session_state["df_estoque"] = df
            elif tipo == "cadastro":
                st.session_state["df_cadastro"] = df

# =========================
# RESULTADO
# =========================
df_e = st.session_state["df_estoque"]
df_c = st.session_state["df_cadastro"]

if df_e is not None:
    st.subheader("📦 Estoque")
    st.dataframe(df_e.head())

if df_c is not None:
    st.subheader("📋 Cadastro")
    st.dataframe(df_c.head())

# =========================
# DOWNLOAD
# =========================
if df_e is not None or df_c is not None:
    zip_final = gerar_zip(df_e, df_c)

    st.download_button(
        "📦 Baixar ZIP Final",
        zip_final,
        file_name="resultado_final.zip"
    )

# =========================
# LOG
# =========================
if st.session_state["logs"]:
    st.subheader("🧾 Logs")
    st.text("\n".join(st.session_state["logs"]))
