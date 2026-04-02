import json
import os
from typing import Dict

from openai import OpenAI

from core.logger import log
from core.utils import limpar, validar_gtin


CAMPOS_PRODUTO = [
    "codigo",
    "gtin",
    "produto",
    "preco",
    "descricao_curta",
    "marca",
    "estoque",
]

TERMOS_PROIBIDOS_LINK = [
    "youtube.com",
    "youtu.be",
    "instagram.com",
    "facebook.com",
    "wa.me",
    "whatsapp",
    "telegram",
    "tiktok",
    "canal",
    "inscreva-se",
    "promo",
    "cupom",
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
        log(f"Secrets indisponível em ai_product_extractor: {e}")

    return ""


def _rejeitar_codigo_ruim(codigo: str) -> bool:
    cod = limpar(codigo).lower()
    return cod in {
        "",
        "id",
        "id produto",
        "id do produto",
        "id item",
        "item id",
        "codigo de barras",
        "código de barras",
        "gtin",
        "ean",
        "produto",
        "nome",
        "descricao",
        "descrição",
    }


def _marca_ruim(marca: str) -> bool:
    marca = limpar(marca).lower()
    return marca in {
        "",
        "mega center",
        "mega center eletrônicos",
        "mega center eletronicos",
    }


def _link_valido_produto(link: str) -> str:
    link = limpar(link)
    if not link:
        return ""

    lk = link.lower()

    if any(t in lk for t in TERMOS_PROIBIDOS_LINK):
        return ""

    if not (
        lk.startswith("http://")
        or lk.startswith("https://")
        or lk.startswith("www.")
        or "/" in lk
    ):
        return ""

    return link


def _normalizar_resposta(dados: dict, link: str = "") -> Dict[str, str]:
    final = {}

    for campo in CAMPOS_PRODUTO:
        final[campo] = limpar(dados.get(campo, ""))

    if _rejeitar_codigo_ruim(final.get("codigo", "")):
        final["codigo"] = ""

    final["gtin"] = validar_gtin(final.get("gtin", ""))

    if _marca_ruim(final.get("marca", "")):
        final["marca"] = ""

    final["link"] = _link_valido_produto(link)

    if not final.get("descricao_curta") and final.get("produto"):
        final["descricao_curta"] = final["produto"]

    return final


def extrair_dados_produto_com_ia(texto_produto: str, link: str = "") -> Dict[str, str]:
    api_key = _obter_openai_api_key()
    if not api_key:
        log("IA extractor: OPENAI_API_KEY não encontrada")
        return {}

    texto_produto = limpar(texto_produto)
    if not texto_produto:
        log("IA extractor: texto do produto vazio")
        return {}

    texto_produto = texto_produto[:5000]

    prompt = f"""
Você extrai dados de páginas de produto para ERP/Bling.

Retorne SOMENTE JSON válido.
Se não existir, devolva string vazia.
Não invente valores.

Campos:
{CAMPOS_PRODUTO}

Regras:
- codigo = SKU/referência/código interno
- nunca use ID genérico
- nunca use GTIN/EAN como codigo
- gtin só se estiver claramente presente
- marca não pode ser o nome da loja
- descricao_curta deve ser curta e objetiva
- estoque pode vir como "0", "10", "Em estoque" ou vazio

Formato:
{{
  "codigo": "",
  "gtin": "",
  "produto": "",
  "preco": "",
  "descricao_curta": "",
  "marca": "",
  "estoque": ""
}}

LINK:
{link}

TEXTO:
{texto_produto}
"""

    try:
        client = OpenAI(api_key=api_key)
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            temperature=0,
        )

        texto = (response.output_text or "").strip()
        log(f"IA extractor raw: {texto[:800]}")

        if not texto:
            return {}

        dados = json.loads(texto)
        if not isinstance(dados, dict):
            return {}

        final = _normalizar_resposta(dados, link=link)
        log(f"IA extractor final: {final}")
        return final

    except Exception as e:
        log(f"ERRO extrair_dados_produto_com_ia: {e}")
        return {}
