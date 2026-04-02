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


def _limpar_nome(nome: str) -> str:
    return (
        str(nome or "")
        .strip()
        .lower()
        .replace("_", " ")
        .replace("-", " ")
        .replace("/", " ")
        .replace("\\", " ")
    )


def _rejeitar_codigo_ruim(nome_coluna: str) -> bool:
    """
    Regras para NÃO aceitar coluna ruim como SKU/código.
    """
    nome = _limpar_nome(nome_coluna)

    rejeitados_exatos = {
        "id",
        "id produto",
        "id do produto",
        "id item",
        "item id",
    }

    if nome in rejeitados_exatos:
        return True

    # se for muito genérico e não tiver pista de sku/código/referência
    if "id" in nome and not any(x in nome for x in [
        "sku",
        "codigo",
        "código",
        "referencia",
        "referência",
        "ref",
    ]):
        return True

    return False


def _score_codigo(nome_coluna: str) -> int:
    """
    Pontuação de prioridade para decidir se a IA escolheu uma boa coluna de código.
    """
    nome = _limpar_nome(nome_coluna)

    if nome == "sku":
        return 100
    if "sku" in nome:
        return 95
    if nome in ["codigo do produto", "código do produto"]:
        return 90
    if "codigo do produto" in nome or "código do produto" in nome:
        return 88
    if "codigo interno" in nome or "código interno" in nome:
        return 85
    if "referencia" in nome or "referência" in nome:
        return 80
    if nome in ["codigo", "código"]:
        return 70
    if "codigo" in nome or "código" in nome:
        return 65
    if nome in ["ref"]:
        return 60
    if "id" in nome:
        return 0

    return 10


def _corrigir_codigo_mapeado(colunas: list[str], coluna_ia: str | None) -> str:
    """
    Aceita a coluna da IA só se ela for boa.
    Caso contrário, tenta escolher uma melhor.
    """
    if coluna_ia and coluna_ia in colunas and not _rejeitar_codigo_ruim(coluna_ia):
        score_ia = _score_codigo(coluna_ia)
        if score_ia >= 60:
            return coluna_ia

    melhor = ""
    melhor_score = 0

    for col in colunas:
        if _rejeitar_codigo_ruim(col):
            continue

        score = _score_codigo(col)
        if score > melhor_score:
            melhor = col
            melhor_score = score

    return melhor


def _filtrar_mapa_ia(mapa: dict, colunas: list[str]) -> Dict[str, str]:
    final = {}

    for campo, coluna in mapa.items():
        if campo not in CAMPOS_ALVO:
            continue

        if coluna not in colunas:
            continue

        # regra especial do código
        if campo == "codigo":
            continue

        final[campo] = coluna

    # trata código separadamente
    coluna_codigo_ia = mapa.get("codigo", "")
    codigo_final = _corrigir_codigo_mapeado(colunas, coluna_codigo_ia)
    if codigo_final:
        final["codigo"] = codigo_final

    return final


def mapear_colunas_com_ia(df: pd.DataFrame) -> Dict[str, str]:
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

REGRAS CRÍTICAS PARA "codigo":
- "codigo" deve ser SKU/código interno/referência do produto
- priorize colunas como:
  SKU, SKU Pai, SKU Filho, Código do Produto, Código Interno, Referência, Ref, Código
- NÃO use coluna chamada apenas ID
- NÃO use coluna de identificador técnico/genérico
- se houver SKU e ID, escolha SKU
- se houver Referência e ID, escolha Referência
- se houver Código do Produto e ID, escolha Código do Produto

REGRAS PARA "gtin":
- só use colunas como GTIN, GTIN/EAN, EAN, Código de Barras
- não confunda GTIN com SKU

REGRAS PARA "produto":
- use nome/título/descrição principal do produto
- não use descrição curta como produto se houver nome melhor

REGRAS GERAIS:
- retorne SOMENTE JSON válido
- não invente colunas
- se não tiver certeza, não inclua o campo
- o valor deve ser exatamente o nome da coluna original

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

        final = _filtrar_mapa_ia(mapa, colunas)

        log(f"IA mapper final: {final}")
        return final

    except Exception as e:
        log(f"ERRO mapear_colunas_com_ia: {e}")
        return {}
