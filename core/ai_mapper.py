import json
import os
from typing import Dict

import pandas as pd
from openai import OpenAI

from core.logger import log


CAMPOS_ALVO = [
    "codigo",
    "gtin",
    "produto",
    "preco",
    "preco_custo",
    "descricao_curta",
    "descricao_complementar",
    "imagem",
    "link",
    "marca",
    "estoque",
    "ncm",
    "origem",
    "peso_liquido",
    "peso_bruto",
    "estoque_minimo",
    "estoque_maximo",
    "unidade",
    "tipo",
    "situacao",
]


def _obter_openai_api_key():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if api_key:
        return api_key

    try:
        import streamlit as st

        if "OPENAI_API_KEY" in st.secrets:
            api_key = str(st.secrets["OPENAI_API_KEY"]).strip()
            if api_key:
                return api_key
    except Exception as e:
        log(f"Secrets indisponível em ai_mapper: {e}")

    return ""


def _sample_dataframe(df: pd.DataFrame, max_rows: int = 8) -> list[dict]:
    amostra = df.head(max_rows).fillna("").astype(str)
    return amostra.to_dict(orient="records")


def mapear_colunas_com_ia(df: pd.DataFrame) -> Dict[str, str]:
    """
    Retorna um dict no formato:
    {
        "codigo": "SKU",
        "produto": "Nome do Produto"
    }
    """
    if df is None or df.empty:
        log("IA mapper: dataframe vazio")
        return {}

    api_key = _obter_openai_api_key()
    if not api_key:
        log("IA mapper: api_key vazia")
        return {}

    colunas = [str(c) for c in df.columns]
    amostra = _sample_dataframe(df, max_rows=8)

    prompt = f"""
Você é um especialista em mapeamento de planilhas de produtos para ERP/Bling.

Sua tarefa:
1. analisar nomes das colunas
2. analisar a amostra de linhas
3. mapear as colunas para os campos alvo

Campos alvo possíveis:
{CAMPOS_ALVO}

Regras críticas:
- retorne SOMENTE JSON válido
- não invente colunas
- se não tiver certeza, não inclua o campo
- o valor deve ser exatamente o nome da coluna original
- "codigo" deve ser SKU/código interno/referência do produto
- NÃO use coluna genérica "ID" como "codigo" se existir alguma coluna melhor como SKU, Referência, Código, Código do Produto
- "gtin" é EAN/GTIN/código de barras
- "produto" é nome/título/descrição principal
- "descricao_curta" é resumo curto
- "descricao_complementar" é descrição longa/completa
- "imagem" é URL de imagem
- "link" é link externo/url do produto
- "preco_custo" é custo/compra
- "preco" é preço de venda
- "estoque" é saldo/quantidade
- "ncm" é classificação fiscal
- "origem" é origem fiscal
- "peso_liquido" e "peso_bruto" são pesos
- "unidade" é UN, PC etc
- "tipo" geralmente Produto
- "situacao" geralmente Ativo/Inativo

Formato de saída:
{{
  "codigo": "Nome exato da coluna",
  "produto": "Nome exato da coluna"
}}

Colunas disponíveis:
{json.dumps(colunas, ensure_ascii=False)}

Amostra:
{json.dumps(amostra, ensure_ascii=False)}
"""

    try:
        client = OpenAI(api_key=api_key)

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            temperature=0,
        )

        texto = response.output_text.strip()
        log(f"IA mapper raw: {texto[:1200]}")

        mapa = json.loads(texto)

        if not isinstance(mapa, dict):
            log("IA mapper: resposta não é dict")
            return {}

        final = {}
        for campo, coluna in mapa.items():
            if campo in CAMPOS_ALVO and coluna in colunas:
                final[campo] = coluna

        log(f"IA mapper final: {final}")
        return final

    except Exception as e:
        log(f"ERRO mapear_colunas_com_ia: {e}")
        return {}
