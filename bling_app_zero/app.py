import streamlit as st
import pandas as pd

st.set_page_config(page_title="Bling Automação", layout="wide")

st.title("🚀 Bling Automação do Zero")

st.write("Sistema iniciado com sucesso ✅")

# =========================
# UPLOAD
# =========================
st.subheader("📂 Enviar planilha de produtos")

arquivo = st.file_uploader("Escolha um arquivo", type=["xlsx", "csv"])

if arquivo:
    try:
        df = pd.read_excel(arquivo)
        st.success("Arquivo carregado com sucesso!")
        st.dataframe(df.head())
    except:
        st.error("Erro ao ler o arquivo")
