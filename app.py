import streamlit as st
import pandas as pd
import os
from openai import OpenAI

# =========================
# CONFIG
# =========================
st.set_page_config(page_title="IA Planilhas PRO", layout="wide")

st.title("🔥 IA Planilhas PRO")

# =========================
# API KEY
# =========================
try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except:
    st.error("⚠️ Configure sua OPENAI_API_KEY nos Secrets do Streamlit")
    st.stop()

# =========================
# UPLOAD DE ARQUIVO
# =========================
arquivo = st.file_uploader(
    "📂 Envie sua planilha (CSV ou Excel)",
    type=["csv", "xlsx"]
)

df = None

if arquivo is not None:
    try:
        if arquivo.name.endswith(".csv"):
            df = pd.read_csv(arquivo)
        else:
            df = pd.read_excel(arquivo)

        st.success("✅ Arquivo carregado com sucesso!")
        st.dataframe(df)

    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")

# =========================
# PROMPT IA
# =========================
if df is not None:
    pergunta = st.text_area("💬 Pergunte algo sobre sua planilha:")

    if st.button("🚀 Analisar com IA"):
        if pergunta.strip() == "":
            st.warning("Digite uma pergunta")
        else:
            with st.spinner("Processando..."):

                try:
                    # Limita tamanho (evita travar)
                    dados_texto = df.head(50).to_csv(index=False)

                    resposta = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": "Você é um especialista em análise de planilhas."
                            },
                            {
                                "role": "user",
                                "content": f"""
                                Aqui está a planilha:
                                {dados_texto}

                                Pergunta:
                                {pergunta}
                                """
                            }
                        ]
                    )

                    st.subheader("📊 Resposta da IA:")
                    st.write(resposta.choices[0].message.content)

                except Exception as e:
                    st.error(f"Erro na IA: {e}")

# =========================
# DOWNLOAD
# =========================
if df is not None:
    st.download_button(
        "⬇️ Baixar CSV",
        data=df.to_csv(index=False),
        file_name="planilha_processada.csv",
        mime="text/csv"
    )
