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
# LOG
# ==========================================================
try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    try:
        from bling_app_zero.utils.excel import log_debug
    except Exception:
        def log_debug(*args, **kwargs):
            pass


# ==========================================================
# HELPERS
# ==========================================================
def _limpar(valor: Any) -> str:
    return re.sub(r"\s+", " ", str(valor or "")).strip()


def _digitos(valor: Any) -> str:
    return re.sub(r"\D", "", str(valor or ""))


def _safe_list(v: Any) -> list:
    return v if isinstance(v, list) else []


# ==========================================================
# 🔥 NETWORK (API INTERNA)
# ==========================================================
def _buscar_recursivo(obj, chaves, achados):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in chaves and v:
                achados.append(v)
            _buscar_recursivo(v, chaves, achados)
    elif isinstance(obj, list):
        for item in obj:
            _buscar_recursivo(item, chaves, achados)


def _get(obj, keys):
    achados = []
    _buscar_recursivo(obj, set(k.lower() for k in keys), achados)
    return achados[0] if achados else None


def _extrair_network(network_records):
    network_records = _safe_list(network_records)

    melhor = {}
    melhor_score = -1

    for rec in network_records:
        data = rec.get("json")
        if not data:
            continue

        nome = _limpar(_get(data, ["name", "title", "product_name"]))
        preco = numero_texto_crawler(_get(data, ["price", "sale_price", "amount"]))
        desc = _limpar(_get(data, ["description", "short_description"]))
        marca = _limpar(_get(data, ["brand", "manufacturer"]))
        gtin = _digitos(_get(data, ["gtin", "ean"]))
        imagens = _get(data, ["images", "image"])

        if isinstance(imagens, list):
            imagens = " | ".join([i for i in imagens if isinstance(i, str)])

        score = 0
        if nome: score += 3
        if preco: score += 3
        if imagens: score += 2

        if score > melhor_score:
            melhor_score = score
            melhor = {
                "Nome": nome,
                "Preço": preco,
                "Descrição": desc,
                "Marca": marca,
                "GTIN/EAN": gtin,
                "URL Imagens Externas": imagens or "",
            }

    if melhor:
        log_debug(f"[NETWORK] score={melhor_score}")

    return melhor


# ==========================================================
# HTML
# ==========================================================
def extrair_nome(soup, jsonld):
    return (
        texto_limpo_crawler(jsonld.get("name"))
        or meta_content_crawler(soup, "property", "og:title")
        or primeiro_texto_crawler(soup, ["h1"])
    )


def extrair_preco(soup, jsonld, html):
    offers = jsonld.get("offers")
    if isinstance(offers, dict) and offers.get("price"):
        return numero_texto_crawler(offers.get("price"))

    preco = primeiro_texto_crawler(soup, [".price", ".preco"])
    return numero_texto_crawler(preco)


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

    # HTML BASE
    base = {
        "Nome": extrair_nome(soup, json_produto),
        "Preço": extrair_preco(soup, json_produto, html),
        "Descrição": texto_limpo_crawler(json_produto.get("description")),
        "Marca": texto_limpo_crawler(json_produto.get("brand")),
        "Categoria": "",
        "GTIN/EAN": _digitos(json_produto.get("gtin13")),
        "NCM": "",
        "URL Imagens Externas": todas_imagens_crawler(soup, url),
        "Link Externo": url,
        "Estoque": detectar_estoque_crawler(html, soup, padrao_disponivel),
    }

    # 🔥 NETWORK
    network = _extrair_network(network_records)

    # 🔥 MERGE INTELIGENTE
    for k, v in network.items():
        if not base.get(k):
            base[k] = v

    base["Descrição Curta"] = base.get("Descrição") or base.get("Nome")

    if not base.get("Nome"):
        return {}

    log_debug(f"[EXTRACTOR FINAL] {url}")

    return base
