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


def _texto_bruto(valor: Any) -> str:
    try:
        return str(valor or "").strip()
    except Exception:
        return ""


def _extrair_preco_global(html: str) -> str:
    matches = re.findall(r"R\$\s*\d[\d\.\,]*", html or "", re.I)

    precos = []
    for m in matches:
        p = numero_texto_crawler(m)
        if p:
            try:
                precos.append(float(str(p).replace(".", "").replace(",", ".")))
            except Exception:
                pass

    if not precos:
        return ""

    menor = min(precos)
    return f"{menor:.2f}".replace(".", ",")


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


def _marca_invalida(marca: str) -> bool:
    marca_low = texto_limpo_crawler(marca).lower()

    if not marca_low:
        return True

    invalidas = [
        "mega center",
        "megacenter",
        "mega center eletrônicos",
        "mega center eletronicos",
        "loja",
        "store",
        "shop",
        "eletronicos",
        "eletrônicos",
        "distribuidora",
        "importadora",
    ]

    return any(x in marca_low for x in invalidas)


def _normalizar_marca_texto(marca: str) -> str:
    marca = texto_limpo_crawler(marca)
    if not marca:
        return ""

    marca = re.sub(r"^(marca[:\-\s]+)", "", marca, flags=re.I).strip()
    marca = re.sub(r"\s+", " ", marca).strip(" -|/")

    if len(marca) > 40:
        return ""

    return marca


def _extrair_marca_do_nome(nome: str) -> str:
    nome_limpo = texto_limpo_crawler(nome)
    if not nome_limpo:
        return ""

    nome_upper = nome_limpo.upper()

    marcas_conhecidas = [
        "APPLE",
        "ASUS",
        "AOC",
        "BEHRINGER",
        "BOSCH",
        "BRITANIA",
        "CANON",
        "CORSAIR",
        "DELL",
        "ELGIN",
        "EPSON",
        "FUJIFILM",
        "GOLDENTEC",
        "GOOGLE",
        "GREE",
        "HP",
        "HAYOM",
        "HIKVISION",
        "HISENSE",
        "HOCO",
        "HONOR",
        "HUAWEI",
        "INTELBRAS",
        "JBL",
        "KINGSTON",
        "KNUP",
        "KODAK",
        "LENOVO",
        "LG",
        "LOGITECH",
        "MONDIAL",
        "MOTOROLA",
        "MULTILASER",
        "NIKON",
        "NINTENDO",
        "NOKIA",
        "PHILCO",
        "PHILIPS",
        "POSITIVO",
        "REALME",
        "RING",
        "SAMSUNG",
        "SONY",
        "TCL",
        "TP-LINK",
        "TPLINK",
        "VENTISOL",
        "XIAOMI",
    ]

    especiais = {"JBL", "LG", "HP", "AOC", "TCL"}

    for marca in marcas_conhecidas:
        if nome_upper.startswith(marca + " ") or nome_upper == marca:
            return marca if marca in especiais else marca.title()

    for marca in marcas_conhecidas:
        padrao = r"(^|[\s\-\|/()])" + re.escape(marca) + r"($|[\s\-\|/()])"
        if re.search(padrao, nome_upper):
            return marca if marca in especiais else marca.title()

    return ""


def _normalizar_codigo_sku(valor: Any) -> str:
    texto = _texto_bruto(valor)
    if not texto:
        return ""

    texto = re.sub(
        r"^(c[oó]d(?:igo)?|sku|ref(?:er[eê]ncia)?|modelo)\s*[:\-]?\s*",
        "",
        texto,
        flags=re.I,
    ).strip()

    if not texto:
        return ""

    if len(texto) > 60:
        return ""

    return texto


def _eh_codigo_generico_ruim(valor: str) -> bool:
    v = _texto_bruto(valor).lower()
    if not v:
        return True

    ruins = [
        "indisponivel",
        "indisponível",
        "esgotado",
        "produto",
        "categoria",
        "marca",
    ]
    return any(x == v for x in ruins)


def _normalizar_categoria_texto(valor: Any) -> str:
    texto = texto_limpo_crawler(valor)
    if not texto:
        return ""

    texto = re.sub(r"\s*>\s*", " > ", texto)
    texto = re.sub(r"\s+", " ", texto).strip(" >-|/")

    partes = [p.strip() for p in texto.split(">") if p.strip()]
    partes = [
        p for p in partes
        if p.lower() not in {"home", "início", "inicio", "loja", "shop"}
    ]

    if not partes:
        return ""

    categoria = " > ".join(partes[:4])

    if len(categoria) > 120:
        return ""

    return categoria


def extrair_codigo_sku(soup, jsonld, html: str, nome_produto: str = "") -> str:
    candidatos: list[str] = []

    # 1) JSON-LD
    for campo in ["sku", "mpn", "productID", "productId"]:
        valor = _normalizar_codigo_sku(jsonld.get(campo))
        if valor:
            candidatos.append(valor)

    offers = jsonld.get("offers")
    if isinstance(offers, dict):
        for campo in ["sku", "mpn"]:
            valor = _normalizar_codigo_sku(offers.get(campo))
            if valor:
                candidatos.append(valor)

    if isinstance(offers, list):
        for offer in offers:
            if not isinstance(offer, dict):
                continue
            for campo in ["sku", "mpn"]:
                valor = _normalizar_codigo_sku(offer.get(campo))
                if valor:
                    candidatos.append(valor)

    # 2) meta tags
    for attr, value in [
        ("property", "product:retailer_item_id"),
        ("property", "product:sku"),
        ("name", "sku"),
        ("name", "product:sku"),
    ]:
        valor = _normalizar_codigo_sku(meta_content_crawler(soup, attr, value))
        if valor:
            candidatos.append(valor)

    # 3) HTML visível - CÓD / SKU / REF / MODELO
    html_texto = texto_limpo_crawler(BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True))

    padroes = [
        r"\bC[ÓO]D(?:IGO)?\s*[:\-]?\s*([A-Z0-9\-_./]{4,})",
        r"\bSKU\s*[:\-]?\s*([A-Z0-9\-_./]{4,})",
        r"\bREF(?:ER[ÊE]NCIA)?\s*[:\-]?\s*([A-Z0-9\-_./]{4,})",
        r"\bMODELO\s*[:\-]?\s*([A-Z0-9\-_./]{4,})",
    ]

    for padrao in padroes:
        for match in re.findall(padrao, html_texto, flags=re.I):
            valor = _normalizar_codigo_sku(match)
            if valor:
                candidatos.append(valor)

    # 4) elementos comuns no HTML
    for sel in [
        "[class*='sku']",
        "[id*='sku']",
        "[class*='codigo']",
        "[id*='codigo']",
        "[class*='cod']",
        "[id*='cod']",
        "[class*='ref']",
        "[id*='ref']",
        "[class*='modelo']",
        "[id*='modelo']",
    ]:
        for el in soup.select(sel)[:10]:
            txt = _normalizar_codigo_sku(el.get_text(" ", strip=True))
            if txt:
                candidatos.append(txt)

    nome_upper = _texto_bruto(nome_produto).upper()
    vistos = set()

    for c in candidatos:
        c = _texto_bruto(c)
        if not c or c in vistos:
            continue
        vistos.add(c)

        if _eh_codigo_generico_ruim(c):
            continue

        if nome_upper and c.upper() in nome_upper and len(c) > 20:
            continue

        return c

    return ""


def extrair_categoria(soup, jsonld):
    # 1) JSON-LD
    categoria = _normalizar_categoria_texto(jsonld.get("category"))
    if categoria:
        return categoria

    # 2) meta
    for attr, value in [
        ("property", "product:category"),
        ("name", "category"),
        ("name", "product:category"),
    ]:
        meta = _normalizar_categoria_texto(meta_content_crawler(soup, attr, value))
        if meta:
            return meta

    # 3) breadcrumb
    for nav in soup.select("nav, .breadcrumb, [class*='bread']"):
        textos = [
            texto_limpo_crawler(x.get_text(" ", strip=True))
            for x in nav.select("a, span")
        ]
        textos = [t for t in textos if t and len(t) < 50]
        if len(textos) >= 2:
            categoria = _normalizar_categoria_texto(" > ".join(textos))
            if categoria:
                return categoria

    return ""


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


def extrair_marca(soup, jsonld, nome_produto: str = ""):
    marca = jsonld.get("brand")

    if isinstance(marca, dict):
        nome = _normalizar_marca_texto(marca.get("name", ""))
        if nome and not _marca_invalida(nome):
            return nome

    if isinstance(marca, str):
        nome = _normalizar_marca_texto(marca)
        if nome and not _marca_invalida(nome):
            return nome

    meta = _normalizar_marca_texto(meta_content_crawler(soup, "property", "product:brand"))
    if meta and not _marca_invalida(meta):
        return meta

    meta_name = _normalizar_marca_texto(meta_content_crawler(soup, "name", "brand"))
    if meta_name and not _marca_invalida(meta_name):
        return meta_name

    possiveis: list[str] = []

    for sel in [
        "[class*='brand']",
        "[id*='brand']",
        ".marca",
        ".brand",
        "[class*='fabricante']",
        "[id*='fabricante']",
    ]:
        elementos = soup.select(sel)
        for el in elementos[:5]:
            txt = _normalizar_marca_texto(el.get_text(" ", strip=True))
            if txt:
                possiveis.append(txt)

    for m in possiveis:
        if not _marca_invalida(m):
            return m

    marca_nome = _extrair_marca_do_nome(nome_produto)
    if marca_nome and not _marca_invalida(marca_nome):
        return marca_nome

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

    # IA somente em falha total
    if extrair_com_ia and (not nome and not preco):
        log_debug(f"[IA FALLBACK TOTAL] {url}")

        produto_ia = extrair_com_ia(html, url)

        if produto_ia and produto_ia.get("Nome"):
            produto_ia["Descrição Curta"] = produto_ia.get("Descrição") or produto_ia.get("Nome")
            return produto_ia

    if not nome:
        return {}

    codigo_sku = extrair_codigo_sku(soup, json_produto, html, nome)

    base = {
        "Nome": nome,
        "Preço": extrair_preco(soup, json_produto, html),
        "Descrição": extrair_descricao(soup, json_produto),
        "Marca": extrair_marca(soup, json_produto, nome),
        "Categoria": extrair_categoria(soup, json_produto),
        "GTIN/EAN": extrair_gtin(json_produto),
        "Código": codigo_sku,
        "SKU": codigo_sku,
        "URL Imagens Externas": extrair_imagens(soup, url, json_produto),
        "Link Externo": url,
        "Estoque": detectar_estoque_crawler(html, soup, padrao_disponivel),
    }

    base["Descrição Curta"] = base.get("Descrição") or base.get("Nome")

    log_debug(f"[EXTRACTOR FINAL] {url}")

    return base
