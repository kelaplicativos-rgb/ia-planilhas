import json
import pandas as pd
import streamlit as st
import openai


# =========================
# CLIENTE IA
# =========================
def _get_client():
    return openai.OpenAI(
        api_key=st.secrets["OPENAI_API_KEY"]
    )


# =========================
# AMOSTRA
# =========================
def _sample_dataframe(df: pd.DataFrame, max_rows: int = 5):
    return df.head(max_rows).to_dict(orient="records")


# =========================
# IA DETECÇÃO DE COLUNAS
# =========================
def detectar_colunas_com_ia(df: pd.DataFrame) -> dict:
    """
    Usa IA para identificar colunas da planilha.
    Retorna um dicionário com o mapeamento lógico.
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
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é especialista em ERP Bling."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        texto = response.choices[0].message.content.strip()

        # segurança extra (às vezes a IA manda texto + json)
        inicio = texto.find("{")
        fim = texto.rfind("}") + 1
        texto_json = texto[inicio:fim]

        resultado = json.loads(texto_json)

        return resultado

    except Exception as e:
        st.warning(f"⚠️ IA falhou, usando fallback local: {e}")
        return {}
