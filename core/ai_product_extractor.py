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

TERMOS_PROIBIDOS_COLUNA = [
    "video",
    "vídeo",
    "youtube",
    "canal",
    "whatsapp",
    "instagram",
    "facebook",
    "telegram",
    "tiktok",
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
    if not cod:
        return True

    rejeitados = {
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

    return cod in rejeitados


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


def _imagem_valida(imagem: str) -> str:
    imagem = limpar(imagem)
    if not imagem:
        return ""

    lk = imagem.lower()

    if any(t in lk for t in TERMOS_PROIBIDOS_LINK):
        return ""

    return imagem


def _normalizar_resposta(dados: dict, link: str = "") -> Dict[str, str]:
    final = {}

    for campo in CAMPOS_PRODUTO:
        valor = dados.get(campo, "")
        final[campo] = limpar(valor)

    if _rejeitar_codigo_ruim(final.get("codigo", "")):
        final["codigo"] = ""

    final["gtin"] = validar_gtin(final.get("gtin", ""))

    final["link"] = _link_valido_produto(final.get("link", "")) or limpar(link)
    final["imagem"] = _imagem_valida(final.get("imagem", ""))

    if not final.get("descricao_curta") and final.get("produto"):
        final["descricao_curta"] = final["produto"]

    return final


def extrair_dados_produto_com_ia(texto_produto: str, link: str = "") -> Dict[str, str]:
    api_key = _obter_openai_api_key()
    if not api_key:
        log("IA extractor: OPENAI_API_KEY não encontrada")
        return {}

    if not texto_produto or not limpar(texto_produto):
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
- não inferir códigos que não estejam claramente presentes

CAMPOS:
- codigo
- gtin
- produto
- preco
- preco_custo
- descricao_curta
- descricao_complementar
- imagem
- link
- marca
- estoque
- ncm
- origem
- peso_liquido
- peso_bruto
- estoque_minimo
- estoque_maximo
- unidade
- tipo
- situacao

REGRAS CRÍTICAS:
1. "codigo" deve ser SKU/referência/código interno do produto
2. NUNCA use "ID" genérico como codigo
3. NUNCA use GTIN/EAN como codigo
4. "gtin" só deve ser preenchido se estiver claramente identificado como GTIN, EAN ou código de barras
5. Se houver dúvida no GTIN, deixe vazio
6. "produto" é o nome principal/título do produto
7. "descricao_curta" é resumo curto
8. "descricao_complementar" é descrição longa
9. "preco" é preço de venda
10. "preco_custo" só se existir claramente
11. "imagem" só deve ser URL da imagem do produto
12. "link" deve ser o link do próprio produto
13. NUNCA use link de vídeo, canal, propaganda, YouTube, WhatsApp, Instagram ou rede social
14. "estoque" só se existir claramente
15. "tipo" e "situacao" podem ficar vazios se não estiverem claros

FORMATO OBRIGATÓRIO:
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

LINK DA PÁGINA:
{link}

TEXTO BRUTO DA PÁGINA:
{texto_produto[:20000]}
"""

    try:
        client = OpenAI(api_key=api_key)

        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            temperature=0,
        )

        texto = (response.output_text or "").strip()
        log(f"IA extractor raw: {texto[:1500]}")

        if not texto:
            log("IA extractor: resposta vazia")
            return {}

        dados = json.loads(texto)

        if not isinstance(dados, dict):
            log("IA extractor: resposta não é dict")
            return {}

        final = _normalizar_resposta(dados, link=link)
        log(f"IA extractor final: {final}")
        return final

    except Exception as e:
        log(f"ERRO extrair_dados_produto_com_ia: {e}")
        return {}
