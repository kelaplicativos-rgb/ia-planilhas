import streamlit as st
import pandas as pd
from openai import OpenAI

# CONFIG
st.set_page_config(page_title="IA Planilhas PRO", layout="wide")

# API
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# TÍTULO
st.title("🤖 IA Planilhas PRO")
st.markdown("Automação inteligente para planilhas + IA")

# -------------------------
# ABA 1 - CHAT IA
# -------------------------
st.subheader("💬 Pergunte para a IA")

pergunta = st.text_input("Digite sua pergunta:")

if pergunta:
    resposta = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": pergunta}
        ]
    )

    st.success(resposta.choices[0].message.content)

# -------------------------
# ABA 2 - PLANILHA
# -------------------------
st.subheader("📊 Upload de Planilha")

arquivo = st.file_uploader("Envie um arquivo CSV", type=["csv"])

if arquivo:
    df = pd.read_csv(arquivo)

    st.write("### 📄 Dados carregados:")
    st.dataframe(df)

    # Estatísticas básicas
    st.write("### 📈 Estatísticas:")
    st.write(df.describe())

    # Pergunta sobre a planilha
    pergunta_df = st.text_input("Pergunte algo sobre a planilha:")

    if pergunta_df:
        resposta_df = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": f"""
                    Analise essa tabela:
                    {df.head(20).to_string()}

                    Pergunta: {pergunta_df}
                    """
                }
            ]
        )

        st.success(resposta_df.choices[0].message.content)

# -------------------------
# RODAPÉ
# -------------------------
st.markdown("---")
st.markdown("🚀 Desenvolvido com Streamlit + OpenAI")
