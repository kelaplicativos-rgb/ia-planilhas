import json
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


def _sample_dataframe(df: pd.DataFrame, max_rows: int = 5) -> list[dict]:
    amostra = df.head(max_rows).fillna("").astype(str)
    return amostra.to_dict(orient="records")


def mapear_colunas_com_ia(df: pd.DataFrame, api_key: str) -> Dict[str, str]:
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

    if not api_key:
        log("IA mapper: api_key vazia")
        return {}

    colunas = [str(c) for c in df.columns]
    amostra = _sample_dataframe(df, max_rows=5)

    prompt = f"""
Você é um especialista em mapeamento de planilhas de produtos para ERP/Bling.

Sua tarefa:
1. analisar os nomes das colunas
2. analisar a amostra de linhas
3. descobrir qual coluna corresponde a cada campo alvo

Campos alvo possíveis:
{CAMPOS_ALVO}

Regras:
- retorne SOMENTE JSON válido
- não invente coluna que não exista
- se não tiver certeza de um campo, não inclua
- o valor deve ser exatamente o nome da coluna original
- "codigo" é SKU/código interno do produto
- "gtin" é EAN/código de barras
- "produto" é nome/título/descrição principal
- "descricao_curta" é resumo curto
- "descricao_complementar" é descrição longa/completa
- "imagem" é url de imagem
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
        log(f"IA mapper raw: {texto[:1000]}")

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
