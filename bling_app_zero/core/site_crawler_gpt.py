
from __future__ import annotations

import json
import os

from bs4 import BeautifulSoup

from bling_app_zero.core.site_crawler_cleaners import (
    descricao_detalhada_valida,
    normalizar_imagens,
    normalizar_preco_para_planilha,
    safe_str,
)

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


def get_openai_client_and_model():
    api_key = os.getenv("OPENAI_API_KEY", "")
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    try:
        import streamlit as st

        if hasattr(st, "secrets"):
            openai_section = st.secrets.get("openai", {})
            if isinstance(openai_section, dict):
                api_key = api_key or openai_section.get("api_key", "")
                model = openai_section.get("model", model) or model
    except Exception:
        pass

    if not api_key or OpenAI is None:
        return None, model

    try:
        return OpenAI(api_key=api_key), model
    except Exception:
        return None, model


def gpt_extrair_produto(url_produto: str, html: str, heuristica: dict) -> dict:
    client, model = get_openai_client_and_model()
    if client is None:
        return heuristica

    soup = BeautifulSoup(html, "lxml")
    texto_limpo = soup.get_text(" ", strip=True)[:20000]

    prompt = f"""
Extraia dados de produto a partir da página de fornecedor.

URL: {url_produto}
Heurística inicial: {json.dumps(heuristica, ensure_ascii=False)}
Texto da página: {texto_limpo}

Responda SOMENTE em JSON válido:
{{
  "codigo": "",
  "descricao": "",
  "descricao_detalhada": "",
  "categoria": "",
  "gtin": "",
  "ncm": "",
  "preco": "",
  "quantidade": "",
  "url_imagens": ""
}}

Regras:
- não invente
- se não tiver dado, deixe vazio
- se a página não for produto real, deixe tudo vazio
- se encontrar sem estoque, quantidade = "0"
- url_imagens com separador |
- preco no formato 19,90
"""

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": "Responda apenas JSON válido."},
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content or "{}"
        data = json.loads(content)

        return {
            "url_produto": url_produto,
            "codigo": safe_str(data.get("codigo")) or heuristica.get("codigo", ""),
            "descricao": safe_str(data.get("descricao")) or heuristica.get("descricao", ""),
            "descricao_detalhada": descricao_detalhada_valida(
                safe_str(data.get("descricao_detalhada")) or heuristica.get("descricao_detalhada", ""),
                safe_str(data.get("descricao")) or heuristica.get("descricao", ""),
            ),
            "categoria": safe_str(data.get("categoria")) or heuristica.get("categoria", ""),
            "gtin": safe_str(data.get("gtin")) or heuristica.get("gtin", ""),
            "ncm": safe_str(data.get("ncm")) or heuristica.get("ncm", ""),
            "preco": normalizar_preco_para_planilha(
                safe_str(data.get("preco")) or heuristica.get("preco", "")
            ),
            "quantidade": safe_str(data.get("quantidade")) or heuristica.get("quantidade", ""),
            "url_imagens": normalizar_imagens(
                safe_str(data.get("url_imagens")) or heuristica.get("url_imagens", "")
            ),
            "fonte_extracao": "gpt",
        }
    except Exception:
        return heuristica
