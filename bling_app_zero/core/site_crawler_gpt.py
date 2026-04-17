
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


# ============================================================
# CONFIG OPENAI
# ============================================================

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


# ============================================================
# HELPERS
# ============================================================

def _descricao_curta(descricao: str, descricao_detalhada: str) -> str:
    if descricao:
        return descricao[:120]
    if descricao_detalhada:
        return descricao_detalhada[:120]
    return ""


def _quantidade_normalizada(valor: str, texto_base: str) -> str:
    valor = safe_str(valor)

    if valor:
        return valor

    texto = texto_base.lower()

    if any(x in texto for x in ["sem estoque", "indisponível", "indisponivel", "esgotado", "zerado"]):
        return "0"

    return "1"


# ============================================================
# GPT EXTRAÇÃO
# ============================================================

def gpt_extrair_produto(url_produto: str, html: str, heuristica: dict) -> dict:
    client, model = get_openai_client_and_model()

    # fallback TOTAL (sem GPT)
    if client is None:
        heuristica["descricao_curta"] = _descricao_curta(
            heuristica.get("descricao", ""),
            heuristica.get("descricao_detalhada", "")
        )
        heuristica["marca"] = heuristica.get("marca", "")
        heuristica["quantidade"] = _quantidade_normalizada(
            heuristica.get("quantidade", ""),
            heuristica.get("descricao_detalhada", "")
        )
        return heuristica

    soup = BeautifulSoup(html, "lxml")
    texto_limpo = soup.get_text(" ", strip=True)[:20000]

    prompt = f"""
Extraia dados COMPLETOS de produto para integração com ERP Bling.

URL: {url_produto}

Dados iniciais:
{json.dumps(heuristica, ensure_ascii=False)}

Texto da página:
{texto_limpo}

Retorne JSON válido:

{{
  "codigo": "",
  "descricao": "",
  "descricao_curta": "",
  "descricao_detalhada": "",
  "categoria": "",
  "marca": "",
  "gtin": "",
  "ncm": "",
  "preco": "",
  "quantidade": "",
  "url_imagens": ""
}}

REGRAS CRÍTICAS:
- NÃO INVENTAR dados
- Priorizar dados reais da página
- descrição_curta deve ser resumo
- marca deve ser identificada (se existir)
- quantidade:
    - 0 se indisponível
    - 1 se disponível
- url_imagens separado por |
- preco formato 19,90
- se não for produto → tudo vazio
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

        try:
            data = json.loads(content)
        except Exception:
            return heuristica

        descricao = safe_str(data.get("descricao")) or heuristica.get("descricao", "")
        descricao_detalhada = descricao_detalhada_valida(
            safe_str(data.get("descricao_detalhada")) or heuristica.get("descricao_detalhada", ""),
            descricao,
        )

        final = {
            "url_produto": url_produto,
            "codigo": safe_str(data.get("codigo")) or heuristica.get("codigo", ""),
            "descricao": descricao,
            "descricao_curta": safe_str(data.get("descricao_curta")) or _descricao_curta(descricao, descricao_detalhada),
            "descricao_detalhada": descricao_detalhada,
            "categoria": safe_str(data.get("categoria")) or heuristica.get("categoria", ""),
            "marca": safe_str(data.get("marca")) or heuristica.get("marca", ""),
            "gtin": safe_str(data.get("gtin")) or heuristica.get("gtin", ""),
            "ncm": safe_str(data.get("ncm")) or heuristica.get("ncm", ""),
            "preco": normalizar_preco_para_planilha(
                safe_str(data.get("preco")) or heuristica.get("preco", "")
            ),
            "quantidade": _quantidade_normalizada(
                safe_str(data.get("quantidade")) or heuristica.get("quantidade", ""),
                texto_limpo,
            ),
            "url_imagens": normalizar_imagens(
                safe_str(data.get("url_imagens")) or heuristica.get("url_imagens", "")
            ),
            "fonte_extracao": "gpt",
        }

        return final

    except Exception:
        return heuristica
