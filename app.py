import streamlit as st
import pandas as pd
import zipfile
import io
import os
import re
from datetime import datetime

st.set_page_config(page_title="🔥 BLING 100% COMPATÍVEL", layout="wide")
st.title("🔥 BLING 100% COMPATÍVEL")

# =========================
# LOG
# =========================
if "logs" not in st.session_state:
    st.session_state["logs"] = []

def log(msg):
    t = datetime.now().strftime("%H:%M:%S")
    st.session_state["logs"].append(f"[{t}] {msg}")

# =========================
# LIMPEZA
# =========================
def limpar_texto(x):
    if pd.isna(x):
        return ""
    x = str(x).strip()
    x = re.sub(r"\s+", " ", x)
    return x

def corrigir_preco(x):
    try:
        x = str(x).replace(".", "").replace(",", ".")
        v = float(x)
        if v > 1000:
            v = v / 100
        return round(v, 2)
    except:
        return 0.0

def para_int(x):
    try:
        return int(float(str(x).replace(",", ".")))
    except:
        return 0

# =========================
# LEITURA
# =========================
def ler(file):
    if file.name.endswith(".csv"):
        try:
            return pd.read_csv(file, sep=None, engine="python", encoding="utf-8")
        except:
            file.seek(0)
            return pd.read_csv(file, sep=None, engine="python", encoding="latin-1")
    else:
        return pd.read_excel(file)

# =========================
# IDENTIFICAÇÃO
# =========================
def tipo(df):
    cols = " ".join(df.columns).lower()

    if "balan" in cols:
        return "estoque"
    if "descricao" in cols:
        return "cadastro"

    return None

# =========================
# BLING ESTOQUE (OFICIAL)
# =========================
def gerar_estoque(df):
    resultado = pd.DataFrame()

    codigo = df.columns[0]
    estoque = [c for c in df.columns if "balan" in c.lower()]

    estoque = estoque[0] if estoque else None

    resultado["Código"] = df[codigo].apply(limpar_texto)
    resultado["Depósito"] = "Geral"
    resultado["Estoque"] = df[estoque].apply(para_int) if estoque else 0

    resultado = resultado.drop_duplicates(subset=["Código"])

    log("Estoque formatado para Bling")

    return resultado

# =========================
# BLING CADASTRO (OFICIAL)
# =========================
def gerar_cadastro(df):
    resultado = pd.DataFrame()

    codigo = [c for c in df.columns if "codigo" in c.lower()][0]
    descricao = [c for c in df.columns if "descricao" in c.lower()][0]

    preco = None
    for c in df.columns:
        if "preco" in c.lower():
            preco = c

    link = None
    for c in df.columns:
        if "link" in c.lower():
            link = c

    resultado["Código"] = df[codigo].apply(limpar_texto)
    resultado["Descrição"] = df[descricao].apply(limpar_texto)
    resultado["Unidade"] = "UN"
    resultado["Preço"] = df[preco].apply(corrigir_preco) if preco else 0
    resultado["Situação"] = "Ativo"
    resultado["Marca"] = ""
    resultado["Descrição Curta"] = resultado["Descrição"]
    resultado["URL Imagens Externas"] = ""
    resultado["Link Externo"] = df[link] if link else ""

    resultado = resultado.drop_duplicates(subset=["Código"])

    log("Cadastro formatado para Bling")

    return resultado

# =========================
# ZIP FINAL
# =========================
def gerar_zip(est, cad):
    mem = io.BytesIO()

    with zipfile.ZipFile(mem, "w") as z:
        b1 = io.BytesIO()
        est.to_excel(b1, index=False)
        z.writestr("atualizar_estoque.xlsx", b1.getvalue())

        b2 = io.BytesIO()
        cad.to_excel(b2, index=False)
        z.writestr("cadastrar_produtos.xlsx", b2.getvalue())

        z.writestr("log.txt", "\n".join(st.session_state["logs"]))

    mem.seek(0)
    return mem

# =========================
# UPLOAD
# =========================
arquivos = st.file_uploader("Envie as duas planilhas", accept_multiple_files=True)

if arquivos:
    estoque = None
    cadastro = None

    for arq in arquivos:
        df = ler(arq)
        t = tipo(df)

        if t == "estoque":
            estoque = df
        elif t == "cadastro":
            cadastro = df

    if estoque is not None:
        st.success("Estoque carregado")

    if cadastro is not None:
        st.success("Cadastro carregado")

    if estoque is not None and cadastro is not None:

        est_bling = gerar_estoque(estoque)
        cad_bling = gerar_cadastro(cadastro)

        st.subheader("Prévia Estoque")
        st.dataframe(est_bling.head())

        st.subheader("Prévia Cadastro")
        st.dataframe(cad_bling.head())

        zip_final = gerar_zip(est_bling, cad_bling)

        st.download_button("📦 Baixar ZIP Bling", zip_final, "bling_final.zip")

# =========================
# LOG
# =========================
if st.session_state["logs"]:
    st.subheader("Logs")
    st.text("\n".join(st.session_state["logs"]))
