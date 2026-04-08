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


def _safe_dict(v: Any) -> dict:
    return v if isinstance(v, dict) else {}


def _extrair_preco_texto_global(html: str) -> str:
    html = html or ""
    padroes = [
        r"R\$\s*\d[\d\.\,]*",
        r"\d[\d\.\,]*\s*R\$",
    ]

    for padrao in padroes:
        achados = re.findall(padrao, html, flags=re.I)
        for item in achados:
            preco = numero_texto_crawler(item)
            if preco:
                return preco

    return ""


def _extrair_categoria(soup: BeautifulSoup) -> str:
    partes = []

    for a in soup.select(".breadcrumb a, nav.breadcrumb a, .breadcrumbs a"):
        txt = texto_limpo_crawler(a.get_text(" ", strip=True))
        if txt and txt.lower() not in {"home", "início", "inicio"}:
            partes.append(txt)

    return " > ".join(dict.fromkeys(partes))


def _extrair_ncm(html: str) -> str:
    texto = _limpar(html)
    m = re.search(r"\bNCM\b[:\s\-]*([0-9\.\-]{8,12})", texto, re.I)
    if m:
        return _digitos(m.group(1))
    return ""


# ==========================================================
# NETWORK (API INTERNA)
# ==========================================================
def _buscar_recursivo(obj, chaves, achados):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in chaves and v not in (None, "", [], {}):
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
        rec = _safe_dict(rec)
        data = rec.get("json")
        if not data:
            continue

        nome = _limpar(_get(data, ["name", "title", "product_name", "productName"]))
        preco = numero_texto_crawler(
            _get(data, ["price", "sale_price", "amount", "final_price", "special_price"])
        )
        desc = _limpar(_get(data, ["description", "short_description", "shortDescription"]))
        marca_val = _get(data, ["brand", "manufacturer", "marca"])
        gtin = _digitos(_get(data, ["gtin", "ean", "gtin13", "barcode"]))
        imagens = _get(data, ["images", "image", "image_url", "imageUrl"])

        if isinstance(marca_val, dict):
            marca = _limpar(
                marca_val.get("name") or marca_val.get("label") or marca_val.get("title")
            )
        else:
            marca = _limpar(marca_val)

        if isinstance(imagens, list):
            imagens = " | ".join([i for i in imagens if isinstance(i, str)])
        elif not isinstance(imagens, str):
            imagens = ""

        score = 0
        if nome:
            score += 3
        if preco:
            score += 3
        if imagens:
            score += 2
        if desc:
            score += 1

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
# HTML EXTRAÇÃO
# ==========================================================
def extrair_nome(soup, jsonld):
    return (
        texto_limpo_crawler(jsonld.get("name"))
        or meta_content_crawler(soup, "property", "og:title")
        or primeiro_texto_crawler(
            soup,
            ["h1", ".product-title", ".product-name", "[itemprop='name']"],
        )
    )


def extrair_preco(soup, jsonld, html):
    offers = jsonld.get("offers")

    if isinstance(offers, dict) and offers.get("price"):
        preco = numero_texto_crawler(offers.get("price"))
        if preco:
            return preco

    if isinstance(offers, list):
        for item in offers:
            if isinstance(item, dict) and item.get("price"):
                preco = numero_texto_crawler(item.get("price"))
                if preco:
                    return preco

    meta = meta_content_crawler(soup, "property", "product:price:amount")
    if meta:
        preco = numero_texto_crawler(meta)
        if preco:
            return preco

    seletores = [
        ".price",
        ".preco",
        ".product-price",
        ".sale-price",
        ".current-price",
        "[class*='price']",
        "[data-price]",
    ]

    preco = primeiro_texto_crawler(soup, seletores)
    preco = numero_texto_crawler(preco)
    if preco:
        return preco

    return _extrair_preco_texto_global(html)


def extrair_imagens(soup, url, jsonld):
    imgs_json = jsonld.get("image")

    if isinstance(imgs_json, list):
        filtradas = [i for i in imgs_json if isinstance(i, str) and i.strip()]
        if filtradas:
            return " | ".join(filtradas)

    if isinstance(imgs_json, str) and imgs_json.strip():
        return imgs_json.strip()

    return todas_imagens_crawler(soup, url)


def extrair_descricao(soup, jsonld):
    desc = texto_limpo_crawler(jsonld.get("description"))
    if desc:
        return desc

    meta = meta_content_crawler(soup, "name", "description")
    if meta:
        return meta

    return primeiro_texto_crawler(
        soup,
        [
            ".product-description",
            ".description",
            "#tab-description",
            "[itemprop='description']",
        ],
    )


def extrair_marca(jsonld):
    marca = jsonld.get("brand")

    if isinstance(marca, dict):
        return texto_limpo_crawler(
            marca.get("name") or marca.get("label") or marca.get("title")
        )

    if isinstance(marca, str):
        return texto_limpo_crawler(marca)

    return ""


# ==========================================================
# MERGE
# ==========================================================
def _merge_preferindo_melhor(base: dict, network: dict) -> dict:
    if not network:
        return base

    saida = dict(base)

    campos_prioritarios_network = {
        "Preço",
        "GTIN/EAN",
        "URL Imagens Externas",
    }

    for k, v in network.items():
        if not v:
            continue

        if k in campos_prioritarios_network:
            saida[k] = v
            continue

        if not saida.get(k):
            saida[k] = v

    return saida


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

    base = {
        "Nome": extrair_nome(soup, json_produto),
        "Preço": extrair_preco(soup, json_produto, html),
        "Descrição": extrair_descricao(soup, json_produto),
        "Marca": extrair_marca(json_produto),
        "Categoria": _extrair_categoria(soup),
        "GTIN/EAN": _digitos(json_produto.get("gtin13") or json_produto.get("gtin")),
        "NCM": _extrair_ncm(html),
        "URL Imagens Externas": extrair_imagens(soup, url, json_produto),
        "Link Externo": url,
        "Estoque": detectar_estoque_crawler(html, soup, padrao_disponivel),
    }

    network = _extrair_network(network_records)
    base = _merge_preferindo_melhor(base, network)

    base["Descrição Curta"] = base.get("Descrição") or base.get("Nome")

    if not base.get("Nome"):
        return {}

    log_debug(f"[EXTRACTOR FINAL] {url}")

    return base
