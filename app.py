import streamlit as st
import pandas as pd
import re
import json
from openai import OpenAI

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="🔥 Bling IA PRO", layout="wide")
st.title("🔥 Automação Inteligente Bling (IA PRO)")

# =========================
# OPENAI
# =========================
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except:
    st.error("⚠️ Configure sua OPENAI_API_KEY nos Secrets")
    st.stop()

# =========================
# LEITURA ROBUSTA
# =========================
def ler_arquivo(arquivo):
    try:
        return pd.read_csv(
            arquivo,
            sep=None,
            engine="python",
            encoding="utf-8",
            on_bad_lines="skip"
        )
    except:
        return pd.read_csv(
            arquivo,
            sep=";",
            encoding="latin-1",
            on_bad_lines="skip"
        )

# =========================
# VALIDAR GTIN
# =========================
def validar_gtin(gtin):
    gtin = str(gtin)
    gtin = re.sub(r"\D", "", gtin)

    if len(gtin) != 13:
        return ""

    soma = sum((int(n) * (1 if i % 2 == 0 else 3)) for i, n in enumerate(gtin[:-1]))
    digito = (10 - (soma % 10)) % 10

    return gtin if digito == int(gtin[-1]) else ""

# =========================
# IA MAPEAR COLUNAS
# =========================
def mapear_com_ia(df):
    colunas = list(df.columns)
    amostra = df.head(5).to_dict()

    prompt = f"""
    Você é especialista em e-commerce e Bling.

    Analise as colunas abaixo e retorne um JSON mapeando:

    codigo, descricao, preco, estoque, marca, categoria, gtin

    IMPORTANTE:
    - A coluna que representa o nome ou descrição do produto deve ser usada como "descricao".
    - Responda SOMENTE JSON válido.

    Colunas:
    {colunas}

    Dados:
    {amostra}
    """

    resposta = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    try:
        mapa = json.loads(resposta.choices[0].message.content)
    except:
        st.error("❌ Erro ao interpretar resposta da IA")
        mapa = {}

    return mapa

# =========================
# GERAR CADASTRO
# =========================
def gerar_cadastro(df, mapa):
    novo = pd.DataFrame()

    def get(col):
        return df[mapa[col]] if col in mapa and mapa[col] in df.columns else ""

    novo["Código"] = get("codigo")

    # 🔥 REGRA FINAL
    novo["Descrição"] = ""
    novo["Descrição Curta"] = get("descricao")

    novo["Marca"] = get("marca")
    novo["Categoria"] = get("categoria")
    novo["Preço"] = get("preco")
    novo["Estoque"] = get("estoque")
    novo["Unidade"] = "UN"
    novo["Situação"] = "Ativo"

    if "gtin" in mapa:
        novo["GTIN/EAN"] = df[mapa["gtin"]].apply(validar_gtin)
    else:
        novo["GTIN/EAN"] = ""

    return novo

# =========================
# GERAR ESTOQUE
# =========================
def gerar_estoque(df, mapa):
    novo = pd.DataFrame()

    def get(col):
        return df[mapa[col]] if col in mapa and mapa[col] in df.columns else ""

    novo["Codigo produto *"] = get("codigo")
    novo["Descrição Produto"] = get("descricao")
    novo["Deposito"] = "Geral"
    novo["Balanço"] = get("estoque")
    novo["Preço unitário"] = get("preco")

    if "gtin" in mapa:
        novo["GTIN"] = df[mapa["gtin"]].apply(validar_gtin)
    else:
        novo["GTIN"] = ""

    return novo

# =========================
# UPLOAD
# =========================
arquivo = st.file_uploader("📂 Envie qualquer planilha", type=["csv", "xlsx"])

if arquivo:
    try:
        if arquivo.name.endswith(".csv"):
            df = ler_arquivo(arquivo)
        else:
            df = pd.read_excel(arquivo)

        st.success("✅ Planilha carregada")
        st.dataframe(df)

        with st.spinner("🤖 IA analisando colunas..."):
            mapa = mapear_com_ia(df)

        st.subheader("🧠 Mapeamento detectado pela IA")
        st.json(mapa)

        cadastro = gerar_cadastro(df, mapa)
        estoque = gerar_estoque(df, mapa)

        st.subheader("📦 Cadastro Bling")
        st.dataframe(cadastro)

        st.subheader("📊 Estoque Bling")
        st.dataframe(estoque)

        col1, col2 = st.columns(2)

        with col1:
            st.download_button(
                "⬇️ Baixar Cadastro",
                data=cadastro.to_csv(index=False),
                file_name="cadastro_bling.csv",
                mime="text/csv"
            )

        with col2:
            st.download_button(
                "⬇️ Baixar Estoque",
                data=estoque.to_csv(index=False),
                file_name="estoque_bling.csv",
                mime="text/csv"
            )

    except Exception as e:
        st.error(f"❌ Erro: {e}")
