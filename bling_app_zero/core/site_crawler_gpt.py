
from __future__ import annotations

import json
import os
import re

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


# =========================
# 🔧 CONFIG OPENAI
# =========================

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


# =========================
# 🔥 LIMPEZA DE MARCA
# =========================

def limpar_marca(marca: str, titulo: str = "") -> str:
    marca = safe_str(marca).strip()
    titulo = safe_str(titulo).strip()

    if not marca:
        return ""

    marca_lower = marca.lower()
    titulo_lower = titulo.lower()

    bloqueadas = [
        "mega center",
        "eletronicos",
        "eletrônicos",
        "loja",
        "store",
        "shop",
        "distribuidora",
        "atacado",
        "varejo",
    ]

    for b in bloqueadas:
        if b in marca_lower:
            return ""

    genericas = {
        "fone", "cabo", "carregador",
        "caixa", "som", "produto",
        "acessorio", "acessório",
        "eletronico", "eletrônico",
        "usb", "bluetooth"
    }

    if marca_lower in genericas:
        return ""

    if len(marca) > 40:
        return ""

    if marca.isdigit():
        return ""

    if titulo_lower and marca_lower == titulo_lower:
        return ""

    if marca.count(" ") >= 4:
        return ""

    return marca


# =========================
# 🔥 INFERÊNCIA VIA TÍTULO
# =========================

def inferir_marca_do_titulo(titulo: str) -> str:
    titulo = safe_str(titulo)

    if not titulo:
        return ""

    palavras_invalidas = {
        "fone", "cabo", "carregador",
        "caixa", "som", "produto",
        "kit", "para", "com",
        "sem", "de", "da", "do",
        "usb", "bluetooth",
        "celular", "smartphone"
    }

    tokens = re.split(r"\s+", titulo)

    for token in tokens[:5]:
        candidato = re.sub(r"[^A-Za-z0-9\-]", "", token)

        if not candidato:
            continue

        if len(candidato) <= 2:
            continue

        if candidato.lower() in palavras_invalidas:
            continue

        if candidato.isdigit():
            continue

        return candidato

    return ""


# =========================
# 🔥 GPT EXTRAÇÃO PRINCIPAL
# =========================

def gpt_extrair_produto(url_produto: str, html: str, heuristica: dict) -> dict:
    client, model = get_openai_client_and_model()

    if client is None:
        return heuristica

    soup = BeautifulSoup(html, "lxml")
    texto_limpo = soup.get_text(" ", strip=True)[:20000]

    prompt = f"""
Extraia dados de produto a partir da página.

URL: {url_produto}
Dados heurísticos: {json.dumps(heuristica, ensure_ascii=False)}
Texto da página: {texto_limpo}

Retorne JSON válido:
{{
  "codigo": "",
  "descricao": "",
  "descricao_detalhada": "",
  "categoria": "",
  "marca": "",
  "gtin": "",
  "ncm": "",
  "preco": "",
  "quantidade": "",
  "url_imagens": ""
}}

Regras:
- não inventar dados
- se não tiver, deixar vazio
- detectar se é produto real
- detectar "sem estoque" → quantidade = "0"
- url_imagens separadas por |
- preco formato 19,90

🔥 IMPORTANTE:
- identificar MARCA corretamente
- se não existir campo de marca, inferir pelo título
- NUNCA usar nome da loja como marca
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

        descricao = safe_str(data.get("descricao")) or safe_str(heuristica.get("descricao"))

        # =========================
        # 🔥 TRATAMENTO DE MARCA
        # =========================

        marca = safe_str(data.get("marca")) or safe_str(heuristica.get("marca"))

        marca = limpar_marca(marca, descricao)

        if not marca:
            marca = inferir_marca_do_titulo(descricao)

        marca = limpar_marca(marca, descricao)

        # =========================
        # 🔥 RETORNO FINAL
        # =========================

        return {
            "url_produto": url_produto,
            "codigo": safe_str(data.get("codigo")) or heuristica.get("codigo", ""),
            "descricao": descricao,
            "descricao_detalhada": descricao_detalhada_valida(
                safe_str(data.get("descricao_detalhada")) or heuristica.get("descricao_detalhada", ""),
                descricao,
            ),
            "categoria": safe_str(data.get("categoria")) or heuristica.get("categoria", ""),
            "marca": marca,
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
        
