from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

from bling_app_zero.core.site_crawler_helpers import (
    buscar_produto_jsonld_crawler,
    detectar_estoque_crawler,
    extrair_json_ld_crawler,
    meta_content_crawler,
    numero_texto_crawler,
    primeiro_texto_crawler,
    todas_imagens_crawler,
    texto_limpo_crawler,
)

# ==========================================================
# VERSION
# ==========================================================
EXTRACTOR_VERSION = "V2_MODULAR_OK"


# ==========================================================
# IA
# ==========================================================
try:
    from bling_app_zero.core.ia_extractor import extrair_com_ia
except Exception:
    extrair_com_ia = None


# ==========================================================
# LOG
# ==========================================================
try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    def log_debug(*args, **kwargs):
        pass


# ==========================================================
# HELPERS
# ==========================================================
def _digitos(valor: Any) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def _extrair_preco_global(html: str) -> str:
    matches = re.findall(r"R\$\s*\d[\d\.\,]*", html or "", re.I)

    precos = []
    for m in matches:
        p = numero_texto_crawler(m)
        if p:
            precos.append(float(p))

    if not precos:
        return ""

    # 🔥 pega o menor valor válido (evita preço parcelado)
    return str(min(precos))


def _limpar_descricao(texto: str) -> str:
    if not texto:
        return ""

    cortes = [
        "produtos relacionados",
        "veja também",
        "formas de pagamento",
        "atendimento",
        "loja física",
    ]

    texto = texto.lower()

    for c in cortes:
        texto = texto.split(c)[0]

    texto = re.sub(r"\s+", " ", texto)

    return texto.strip()[:800]


def _filtrar_imagens(lista: str) -> str:
    if not lista:
        return ""

    imgs = [i.strip() for i in lista.split("|") if i.strip()]

    imgs = [
        i for i in imgs
        if not any(x in i.lower() for x in ["logo", "icon", "placeholder", "thumb"])
    ]

    imgs = list(dict.fromkeys(imgs))

    return " | ".join(imgs[:5])


# ==========================================================
# EXTRAÇÃO
# ==========================================================
def extrair_nome(soup, jsonld):
    return (
        texto_limpo_crawler(jsonld.get("name"))
        or meta_content_crawler(soup, "property", "og:title")
        or primeiro_texto_crawler(
            soup,
            ["h1", ".product-title", ".product-name"],
        )
    )


def extrair_preco(soup, jsonld, html):
    offers = jsonld.get("offers")

    if isinstance(offers, dict):
        preco = numero_texto_crawler(offers.get("price"))
        if preco:
            return preco

    if isinstance(offers, list):
        for o in offers:
            preco = numero_texto_crawler(o.get("price"))
            if preco:
                return preco

    meta = meta_content_crawler(soup, "property", "product:price:amount")
    if meta:
        return numero_texto_crawler(meta)

    return _extrair_preco_global(html)


def extrair_descricao(soup, jsonld):
    desc = texto_limpo_crawler(jsonld.get("description"))

    if not desc:
        meta = meta_content_crawler(soup, "name", "description")
        desc = meta or ""

    if not desc:
        el = soup.select_one("[class*='description']")
        if el:
            desc = texto_limpo_crawler(el.get_text())

    return _limpar_descricao(desc)


def extrair_imagens(soup, url, jsonld):
    imgs = jsonld.get("image")

    if isinstance(imgs, list):
        return _filtrar_imagens(" | ".join(imgs))

    if isinstance(imgs, str):
        return _filtrar_imagens(imgs)

    return _filtrar_imagens(todas_imagens_crawler(soup, url))


def extrair_marca(jsonld):
    marca = jsonld.get("brand")

    if isinstance(marca, dict):
        return texto_limpo_crawler(marca.get("name"))

    if isinstance(marca, str):
        return texto_limpo_crawler(marca)

    return ""


def extrair_gtin(jsonld):
    for campo in ["gtin13", "gtin", "ean"]:
        valor = _digitos(jsonld.get(campo))
        if len(valor) in (8, 12, 13, 14):
            return valor
    return ""


# ==========================================================
# MAIN
# ==========================================================
def extrair_produto_crawler(
    html: str,
    url: str,
    padrao_disponivel: int = 10,
    network_records=None,
    payload_origem=None,
) -> dict:

    soup = BeautifulSoup(html, "html.parser")

    jsonlds = extrair_json_ld_crawler(soup)
    json_produto = buscar_produto_jsonld_crawler(jsonlds)

    nome = extrair_nome(soup, json_produto)
    preco = extrair_preco(soup, json_produto, html)

    # 🔥 IA SOMENTE EM FALHA TOTAL
    if extrair_com_ia and (not nome and not preco):
        log_debug(f"[IA FALLBACK TOTAL] {url}")

        produto_ia = extrair_com_ia(html, url)

        if produto_ia and produto_ia.get("Nome"):
            produto_ia["Descrição Curta"] = produto_ia.get("Descrição") or produto_ia.get("Nome")
            return produto_ia

    if not nome:
        return {}

    base = {
        "Nome": nome,
        "Preço": preco,
        "Descrição": extrair_descricao(soup, json_produto),
        "Marca": extrair_marca(json_produto),
        "Categoria": "",  # 🔥 REMOVIDO AUTO
        "GTIN/EAN": extrair_gtin(json_produto),
        "URL Imagens Externas": extrair_imagens(soup, url, json_produto),
        "Link Externo": url,
        "Estoque": detectar_estoque_crawler(html, soup, padrao_disponivel),
    }

    base["Descrição Curta"] = base.get("Descrição") or base.get("Nome")

    log_debug(f"[EXTRACTOR FINAL] {url}")

    return base
