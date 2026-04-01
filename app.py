import streamlit as st
from openai import OpenAI

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.title("🤖 IA Planilhas PRO")

pergunta = st.text_input("Digite sua pergunta:")

if pergunta:
    resposta = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": pergunta}
        ]
    )

    st.write(resposta.choices[0].message.content)
