
import streamlit as st
import pandas as pd
from bling_app_zero.ui.app_helpers import ir_para_etapa


def render_origem_dados():
    st.title("📥 Origem dos Dados")

    file = st.file_uploader("Envie sua planilha", type=["csv", "xlsx"])

    if file:
        if file.name.endswith(".csv"):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)

        st.session_state["df_origem"] = df

        st.success("Arquivo carregado!")

        st.dataframe(df.head())

        if st.button("Continuar"):
            ir_para_etapa("precificacao")
