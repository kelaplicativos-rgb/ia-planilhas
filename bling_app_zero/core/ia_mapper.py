import json
from typing import Any

import openai
import pandas as pd
import streamlit as st


def _sample_dataframe(df: pd.DataFrame, max_rows: int = 5) -> list[dict[str, Any]]:
    return df.head(max_rows).to_dict(orient="records")


def _extrair_json(texto: str) -> dict:
    texto = str(texto).strip()

    inicio = texto.find("{")
    fim = texto.rfind("}") + 1

    if inicio == -1 or fim <= 0:
        return {}

    trecho = texto[inicio:fim]

    try:
        return json.loads(trecho)
    except Exception:
        return {}


def detectar_colunas_com_ia(df: pd.DataFrame) -> dict:
    """
    Usa IA para identificar colunas da planilha.
    Se a IA falhar, retorna {} e o fallback local assume.
    """
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except Exception:
        return {}

    try:
        # Evita o erro de proxies/httpx no ambiente do Streamlit Cloud
        client = openai.OpenAI(api_key=api_key, max_retries=1)

        colunas = list(df.columns)
        amostra = _sample_dataframe(df)

        prompt = f"""
Você é um especialista em integração com ERP Bling.

Analise uma planilha de produtos e identifique quais colunas representam:

- codigo
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

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é especialista em ERP Bling e planilhas."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )

        texto = response.choices[0].message.content or ""
        resultado = _extrair_json(texto)

        if isinstance(resultado, dict):
            return resultado

        return {}

    except Exception as e:
        st.warning(f"⚠️ IA falhou, usando apenas detecção local: {e}")
        return {}
