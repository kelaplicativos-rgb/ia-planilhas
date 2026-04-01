import streamlit as st
import pandas as pd
from utils import processar

st.set_page_config(page_title="IA Planilhas PRO", layout="wide")

st.title("🚀 Leitor Inteligente de Planilhas com IA")

arquivo = st.file_uploader("Envie sua planilha", type=["xlsx", "csv"])

if arquivo:
    if arquivo.name.endswith(".csv"):
        df = pd.read_csv(arquivo)
    else:
        df = pd.read_excel(arquivo)

    st.dataframe(df.head())

    if st.button("Processar"):
        df_final = processar(df)

        st.dataframe(df_final)

        st.download_button(
            "Baixar CSV",
            df_final.to_csv(index=False),
            "saida.csv"
        )
