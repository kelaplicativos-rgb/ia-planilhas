import json
import os
from typing import Dict

from openai import OpenAI

from core.logger import log
from core.normalizer.cleaners import validar_gtin


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
        log(f"Secrets indisponível em ai_product_extractor: {e}")

    return ""


def extrair_dados_produto_com_ia(texto_produto: str, link: str = "") -> Dict[str, str]:
    api_key = _obter_openai_api_key()
    if not api_key:
        log("IA extractor: OPENAI_API_KEY não encontrada")
        return {}

    if not texto_produto or not str(texto_produto).strip():
        log("IA extractor: texto do produto vazio")
        return {}

    prompt = f"""
Você é um especialista em extração de dados de produtos para cadastro em ERP/Bling.

Sua tarefa:
- analisar o texto bruto de uma página de produto
- identificar os dados do produto
- retornar SOMENTE um JSON válido
- se um campo não existir, retornar string vazia
- não inventar valores

Regras críticas:
- "codigo" deve ser SKU/referência/código do produto, nunca "ID" genérico
- "gtin" só deve ser preenchido se estiver claramente identificado como EAN, GTIN ou código de barras
- se houver dúvida sobre GTIN, deixe vazio

Formato obrigatório:
{{
  "codigo": "",
  "gtin": "",
  "produto": "",
  "preco": "",
  "preco_custo": "",
  "descricao_curta": "",
  "descricao_complementar": "",
  "imagem": "",
  "link": "",
  "marca": "",
  "estoque": "",
  "ncm": "",
  "origem": "",
  "peso_liquido": "",
  "peso_bruto": "",
  "estoque_minimo": "",
  "estoque_maximo": "",
  "unidade": "",
  "tipo": "",
  "situacao": ""
}}

Link da página:
{link}

Texto bruto da página:
{texto_produto[:18000]}
"""

    try:
        client = OpenAI(api_key=api_key)

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            temperature=0,
        )

        texto = response.output_text.strip()
        log(f"IA extractor raw: {texto[:1200]}")

        dados = json.loads(texto)

        if not isinstance(dados, dict):
            log("IA extractor: resposta não é dict")
            return {}

        campos = [
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

        final = {}
        for campo in campos:
            valor = dados.get(campo, "")
            final[campo] = "" if valor is None else str(valor).strip()

        if not final.get("link"):
            final["link"] = str(link).strip()

        if str(final.get("codigo", "")).strip().lower() == "id":
            final["codigo"] = ""

        final["gtin"] = validar_gtin(final.get("gtin", ""))

        log(f"IA extractor final: {final}")
        return final

    except Exception as e:
        log(f"ERRO extrair_dados_produto_com_ia: {e}")
        return {}
