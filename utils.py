from openai import OpenAI
import streamlit as st

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def identificar_colunas_com_ia(df, campos):

    colunas = list(df.columns)

    prompt = f"""
    Mapeie as colunas abaixo para:

    {campos}

    Colunas disponíveis:
    {colunas}

    Retorne JSON:
    """

    resposta = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    try:
        return eval(resposta.choices[0].message.content)
    except:
        return {}

def gerar_descricao_ia(nome):

    if not nome:
        return ""

    resposta = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"Descrição curta: {nome}"}],
        temperature=0.3,
        max_tokens=50
    )

    return resposta.choices[0].message.content.strip()
