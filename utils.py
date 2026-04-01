import pandas as pd
import json
import streamlit as st
from openai import OpenAI

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

def identificar_colunas_com_ia(df):
    colunas = list(df.columns)

    exemplos = {
        col: df[col].astype(str).dropna().head(5).tolist()
        for col in colunas
    }

    prompt = f"""
    Identifique colunas:

    sku, nome, preco, descricao, imagem, estoque

    Responda JSON:

    {{
        "sku": "",
        "nome": "",
        "preco": "",
        "descricao": "",
        "imagem": "",
        "estoque": ""
    }}

    Colunas: {colunas}
    Exemplos: {exemplos}
    """

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    texto = response.choices[0].message.content

    try:
        return json.loads(texto)
    except:
        return {}

def processar(df):
    df.columns = [str(c).lower().strip() for c in df.columns]

    mapa = identificar_colunas_com_ia(df)

    novo = pd.DataFrame()

    for chave, col in mapa.items():
        if col in df.columns:
            novo[chave] = df[col]
        else:
            novo[chave] = ""

    return novo
