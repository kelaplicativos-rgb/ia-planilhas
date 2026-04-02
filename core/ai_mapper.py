import json
import os
from typing import Dict

import pandas as pd
from openai import OpenAI

from core.logger import log
from core.utils import limpar


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

TERMOS_PROIBIDOS_LINK = [
    "video",
    "vídeo",
    "youtube",
    "canal",
    "whatsapp",
    "instagram",
    "facebook",
    "telegram",
    "tiktok",
    "propaganda",
    "promo",
    "cupom",
]

TERMOS_BONS_LINK = [
    "link",
    "url",
    "url produto",
    "produto url",
    "link externo",
    "site produto",
]

TERMOS_BONS_IMAGEM = [
    "imagem",
    "foto",
    "url imagem",
    "url imagens externas",
    "imagem principal",
    "foto principal",
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


def _nome_norm(nome: str) -> str:
    return (
        limpar(nome)
        .lower()
        .replace("_", " ")
        .replace("-", " ")
        .replace("/", " ")
        .replace("\\", " ")
    )


def _rejeitar_coluna_link(nome_coluna: str) -> bool:
    nome = _nome_norm(nome_coluna)
    return any(t in nome for t in TERMOS_PROIBIDOS_LINK)


def _score_link(nome_coluna: str) -> int:
    nome = _nome_norm(nome_coluna)

    if _rejeitar_coluna_link(nome):
        return 0

    if nome in ["link externo", "url produto", "produto url", "link produto"]:
        return 100

    if any(t in nome for t in TERMOS_BONS_LINK):
        return 80

    return 0


def _score_imagem(nome_coluna: str) -> int:
    nome = _nome_norm(nome_coluna)

    if nome in ["url imagens externas", "url imagem", "imagem principal", "foto principal"]:
        return 100

    if any(t in nome for t in TERMOS_BONS_IMAGEM):
        return 80

    return 0


def _corrigir_link_mapeado(colunas: list[str], coluna_ia: str | None) -> str:
    if coluna_ia and coluna_ia in colunas and not _rejeitar_coluna_link(coluna_ia):
        if _score_link(coluna_ia) > 0:
            return coluna_ia

    melhor = ""
    melhor_score = 0

    for col in colunas:
        score = _score_link(col)
        if score > melhor_score:
            melhor = col
            melhor_score = score

    return melhor


def _corrigir_imagem_mapeada(colunas: list[str], coluna_ia: str | None) -> str:
    if coluna_ia and coluna_ia in colunas:
        if _score_imagem(coluna_ia) > 0:
            return coluna_ia

    melhor = ""
    melhor_score = 0

    for col in colunas:
        score = _score_imagem(col)
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
        if campo in ["link", "imagem"]:
            continue
        final[campo] = coluna

    link_final = _corrigir_link_mapeado(colunas, mapa.get("link"))
    if link_final:
        final["link"] = link_final

    imagem_final = _corrigir_imagem_mapeada(colunas, mapa.get("imagem"))
    if imagem_final:
        final["imagem"] = imagem_final

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

REGRAS CRÍTICAS:
- retorne SOMENTE JSON válido
- não invente colunas
- se não tiver certeza, não inclua o campo
- o valor deve ser exatamente o nome da coluna original

REGRAS PARA "imagem":
- só use coluna de imagem/foto/url de imagem
- nunca use link de vídeo, canal ou propaganda

REGRAS PARA "link":
- só use coluna de link/url real do produto
- NUNCA use vídeo
- NUNCA use YouTube
- NUNCA use Instagram/Facebook/WhatsApp
- se a única coluna parecida for vídeo, não inclua "link"

REGRAS PARA "codigo":
- deve ser SKU/código/referência do produto
- não use ID genérico

Colunas disponíveis:
{json.dumps(colunas, ensure_ascii=False)}

Amostra:
{json.dumps(amostra, ensure_ascii=False)}

Formato:
{{
  "codigo": "Nome exato da coluna",
  "produto": "Nome exato da coluna",
  "imagem": "Nome exato da coluna",
  "link": "Nome exato da coluna"
}}
"""

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            temperature=0,
        )

        texto = (response.output_text or "").strip()
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
