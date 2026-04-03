import json
import pandas as pd
import streamlit as st
from openai import OpenAI


def _get_client():
    return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])


def _sample_dataframe(df: pd.DataFrame, max_rows=5):
    return df.head(max_rows).to_dict(orient="records")


def detectar_colunas_com_ia(df: pd.DataFrame) -> dict:
    """
    Usa IA para identificar colunas da planilha.
    Retorna um dict com mapeamento lógico.
    """

    client = _get_client()

    colunas = list(df.columns)
    amostra = _sample_dataframe(df)

    prompt = f"""
Você é um especialista em integração com ERP Bling.

Analise uma planilha de produtos e identifique quais colunas representam:

- codigo (SKU ou código do produto)
- nome
- preco
- descricao_curta
- marca
- imagem
- estoque
- deposito
- situacao
- unidade

Responda SOMENTE em JSON no formato:

{{
  "codigo": "...",
  "nome": "...",
  "preco": "...",
  "descricao_curta": "...",
  "marca": "...",
  "imagem": "...",
  "estoque": "...",
  "deposito": "...",
  "situacao": "...",
  "unidade": "..."
}}

Se não encontrar, use null.

Colunas disponíveis:
{colunas}

Amostra de dados:
{amostra}
"""

    try:
        response = client.responses.create(
            model="gpt-5.3",
            input=prompt
        )

        texto = response.output_text.strip()

        resultado = json.loads(texto)

        return resultado

    except Exception as e:
        st.warning(f"⚠️ IA falhou, usando fallback local: {e}")
        return {}
