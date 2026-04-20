
from __future__ import annotations

import json
import os
import re
from typing import Any

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
# HELPERS DE LIMPEZA
# ============================================================

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
        "ecommerce",
        "e-commerce",
        "site oficial",
        "loja oficial",
        "minha loja",
        "nossa loja",
    ]

    for b in bloqueadas:
        if b in marca_lower:
            return ""

    genericas = {
        "fone",
        "fones",
        "cabo",
        "cabos",
        "carregador",
        "carregadores",
        "caixa",
        "som",
        "produto",
        "produtos",
        "acessorio",
        "acessório",
        "acessorios",
        "acessórios",
        "eletronico",
        "eletrônico",
        "usb",
        "bluetooth",
        "wireless",
        "tipo-c",
        "celular",
        "smartphone",
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


def inferir_marca_do_titulo(titulo: str) -> str:
    titulo = safe_str(titulo)

    if not titulo:
        return ""

    palavras_invalidas = {
        "fone",
        "fones",
        "cabo",
        "cabos",
        "carregador",
        "carregadores",
        "caixa",
        "som",
        "produto",
        "produtos",
        "kit",
        "para",
        "com",
        "sem",
        "de",
        "da",
        "do",
        "usb",
        "bluetooth",
        "wireless",
        "tipo",
        "tipo-c",
        "celular",
        "smartphone",
    }

    tokens = re.split(r"\s+", titulo)

    for token in tokens[:6]:
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


def limpar_codigo(valor: str) -> str:
    texto = safe_str(valor)
    if not texto:
        return ""
    texto = re.sub(r"[\n\r\t]+", " ", texto).strip()
    texto = re.sub(r"\s{2,}", " ", texto)
    return texto[:120]


def limpar_gtin(valor: str) -> str:
    texto = re.sub(r"\D+", "", safe_str(valor))
    if len(texto) in {8, 12, 13, 14}:
        return texto
    return ""


def limpar_ncm(valor: str) -> str:
    texto = re.sub(r"\D+", "", safe_str(valor))
    if len(texto) >= 6:
        return texto[:8]
    return ""


def normalizar_quantidade(valor: str, texto_pagina: str = "") -> str:
    qtd = safe_str(valor)
    if qtd:
        return qtd

    texto_n = safe_str(texto_pagina).lower()

    if any(x in texto_n for x in ["sem estoque", "indisponível", "indisponivel", "esgotado", "zerado", "outofstock"]):
        return "0"

    match = re.search(r"(?:estoque|quantidade|qtd)[^\d]{0,12}(\d{1,5})", texto_n, flags=re.I)
    if match:
        return safe_str(match.group(1))

    if any(x in texto_n for x in ["em estoque", "disponível", "disponivel", "in stock"]):
        return "1"

    return ""


def _json_only(content: str) -> str:
    bruto = safe_str(content)
    if not bruto:
        return "{}"

    bruto = bruto.strip()

    if bruto.startswith("```"):
        bruto = re.sub(r"^```(?:json)?", "", bruto, flags=re.I).strip()
        bruto = re.sub(r"```$", "", bruto).strip()

    match = re.search(r"\{.*\}", bruto, flags=re.S)
    if match:
        return match.group(0).strip()

    return "{}"


def _safe_json_loads(content: str) -> dict[str, Any]:
    try:
        data = json.loads(_json_only(content))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _pagina_parece_login(texto_limpo: str, url_produto: str) -> bool:
    texto_n = safe_str(texto_limpo).lower()
    url_n = safe_str(url_produto).lower()

    sinais = [
        "/login",
        "fazer login",
        "acesse sua conta",
        "insira seus dados",
        "senha",
        "password",
        "g-recaptcha",
        "recaptcha",
        "não sou um robô",
        "nao sou um robo",
    ]

    if any(s in url_n for s in ["/login", "/auth", "/signin"]):
        return True

    if any(s in texto_n for s in sinais):
        return True

    return False


def _construir_prompt(url_produto: str, heuristica: dict[str, Any], texto_limpo: str) -> str:
    heuristica_json = json.dumps(heuristica, ensure_ascii=False)

    return f"""
Você vai completar dados de produto a partir de uma página web.

URL: {url_produto}
Heurística atual: {heuristica_json}
Texto da página: {texto_limpo}

Retorne JSON válido exatamente neste formato:
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
  "url_imagens": "",
  "eh_produto": true,
  "confianca": 0
}}

Regras obrigatórias:
- responda apenas JSON válido
- não invente dados
- se não tiver certeza, deixe vazio
- preserve dados bons da heurística
- só substitua a heurística quando o texto da página indicar claramente valor melhor
- se a página parecer login, dashboard, listagem administrativa ou página sem produto único, marque "eh_produto": false
- se detectar "sem estoque", "indisponível", "esgotado" ou equivalente, quantidade = "0"
- url_imagens deve ficar em string única separada por "|"
- preco deve vir no padrão "19,90"
- não use nome da loja como marca
- se a marca não estiver explícita, tente inferir do título do produto sem inventar
- gtin deve ser apenas número
- ncm deve ser apenas número
- confianca deve ser inteiro de 0 a 100

Prioridade dos campos:
1. descricao
2. codigo
3. marca
4. gtin
5. preco
6. quantidade
7. categoria
8. ncm
9. url_imagens
10. descricao_detalhada
""".strip()


def _fundir_campos(heuristica: dict[str, Any], data: dict[str, Any], texto_limpo: str, url_produto: str) -> dict[str, Any]:
    descricao_heur = safe_str(heuristica.get("descricao"))
    descricao_gpt = safe_str(data.get("descricao"))
    descricao = descricao_gpt or descricao_heur

    codigo = limpar_codigo(safe_str(data.get("codigo")) or safe_str(heuristica.get("codigo")))
    gtin = limpar_gtin(safe_str(data.get("gtin")) or safe_str(heuristica.get("gtin")))
    ncm = limpar_ncm(safe_str(data.get("ncm")) or safe_str(heuristica.get("ncm")))

    marca = safe_str(data.get("marca")) or safe_str(heuristica.get("marca"))
    marca = limpar_marca(marca, descricao)

    if not marca:
        marca = inferir_marca_do_titulo(descricao)
    marca = limpar_marca(marca, descricao)

    preco = normalizar_preco_para_planilha(
        safe_str(data.get("preco")) or safe_str(heuristica.get("preco"))
    )

    quantidade = normalizar_quantidade(
        safe_str(data.get("quantidade")) or safe_str(heuristica.get("quantidade")),
        texto_pagina=texto_limpo,
    ) or safe_str(heuristica.get("quantidade")) or "1"

    url_imagens = normalizar_imagens(
        safe_str(data.get("url_imagens")) or safe_str(heuristica.get("url_imagens"))
    )

    descricao_detalhada = descricao_detalhada_valida(
        safe_str(data.get("descricao_detalhada")) or safe_str(heuristica.get("descricao_detalhada")),
        descricao,
    )

    categoria = safe_str(data.get("categoria")) or safe_str(heuristica.get("categoria"))

    return {
        "url_produto": url_produto,
        "codigo": codigo,
        "descricao": descricao,
        "descricao_detalhada": descricao_detalhada,
        "categoria": categoria,
        "marca": marca,
        "gtin": gtin,
        "ncm": ncm,
        "preco": preco,
        "quantidade": quantidade,
        "url_imagens": url_imagens,
        "fonte_extracao": "gpt",
    }


# ============================================================
# GPT EXTRAÇÃO PRINCIPAL
# ============================================================

def gpt_extrair_produto(url_produto: str, html: str, heuristica: dict) -> dict:
    client, model = get_openai_client_and_model()

    if client is None:
        return heuristica if isinstance(heuristica, dict) else {}

    if not isinstance(heuristica, dict):
        heuristica = {}

    soup = BeautifulSoup(html or "", "lxml")
    texto_limpo = soup.get_text(" ", strip=True)
    texto_limpo = safe_str(texto_limpo)[:22000]

    if not texto_limpo:
        return heuristica

    if _pagina_parece_login(texto_limpo, url_produto):
        return heuristica

    prompt = _construir_prompt(
        url_produto=url_produto,
        heuristica=heuristica,
        texto_limpo=texto_limpo,
    )

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Você extrai dados estruturados de produtos. "
                        "Nunca invente campos ausentes. "
                        "Responda somente JSON."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )

        content = response.choices[0].message.content or "{}"
        data = _safe_json_loads(content)

        if not data:
            return heuristica

        eh_produto = data.get("eh_produto", True)
        try:
            confianca = int(data.get("confianca", 0) or 0)
        except Exception:
            confianca = 0

        if eh_produto is False:
            return heuristica

        resultado = _fundir_campos(
            heuristica=heuristica,
            data=data,
            texto_limpo=texto_limpo,
            url_produto=url_produto,
        )

        # blindagem final: se GPT vier muito fraco, preserva heurística
        campos_relevantes = [
            safe_str(resultado.get("descricao")),
            safe_str(resultado.get("codigo")),
            safe_str(resultado.get("preco")),
            safe_str(resultado.get("url_imagens")),
        ]
        total_preenchidos = sum(1 for x in campos_relevantes if x)

        if confianca < 20 and total_preenchidos <= 1:
            return heuristica

        if not safe_str(resultado.get("descricao")):
            return heuristica

        return resultado

    except Exception:
        return heuristica
