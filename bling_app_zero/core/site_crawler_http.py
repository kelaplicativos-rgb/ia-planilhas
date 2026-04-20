
from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from bling_app_zero.core.site_crawler_cleaners import (
    descricao_detalhada_valida,
    extrair_preco,
    fornecedor_cfg,
    imagem_valida,
    mesmo_dominio,
    normalizar_imagens,
    normalizar_preco_para_planilha,
    normalizar_texto,
    safe_str,
)


# ============================================================
# HELPERS BASE
# ============================================================

def texto_por_selectors(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        try:
            el = soup.select_one(selector)
            if el:
                if el.name == "meta":
                    content = safe_str(el.get("content"))
                    if content:
                        return content
                txt = safe_str(el.get_text(" ", strip=True))
                if txt:
                    return txt
        except Exception:
            continue
    return ""


def imagens_por_selectors(url_produto: str, soup: BeautifulSoup, selectors: list[str]) -> list[str]:
    imagens = []
    vistos = set()

    for selector in selectors:
        try:
            for el in soup.select(selector):
                src = safe_str(
                    el.get("content")
                    or el.get("src")
                    or el.get("data-src")
                    or el.get("data-lazy-src")
                    or el.get("data-zoom-image")
                    or el.get("data-original")
                    or el.get("href")
                )
                if not src:
                    continue

                url_img = urljoin(url_produto, src)
                if not imagem_valida(url_img):
                    continue
                if url_img in vistos:
                    continue

                vistos.add(url_img)
                imagens.append(url_img)
        except Exception:
            continue

    return imagens


def _regex_busca(texto: str, padroes: list[str]) -> str:
    base = safe_str(texto)
    if not base:
        return ""

    for padrao in padroes:
        try:
            match = re.search(padrao, base, flags=re.I)
            if match:
                valor = safe_str(match.group(1))
                if valor:
                    return valor
        except Exception:
            continue

    return ""


def _limpar_codigo(valor: str) -> str:
    texto = safe_str(valor)
    if not texto:
        return ""
    texto = re.sub(r"[\n\r\t]+", " ", texto).strip()
    texto = re.sub(r"\s{2,}", " ", texto)
    return texto[:120]


def _limpar_gtin(valor: str) -> str:
    texto = re.sub(r"\D+", "", safe_str(valor))
    if len(texto) in {8, 12, 13, 14}:
        return texto
    return ""


def _normalizar_quantidade(texto_total: str, quantidade_atual: str = "") -> str:
    qtd = safe_str(quantidade_atual)
    if qtd:
        return qtd

    texto_n = normalizar_texto(texto_total)

    if any(x in texto_n for x in ["sem estoque", "indisponivel", "indisponível", "esgotado", "zerado", "outofstock"]):
        return "0"

    match = re.search(r"(?:estoque|quantidade|qtd)[^\d]{0,12}(\d{1,5})", texto_n, flags=re.I)
    if match:
        return safe_str(match.group(1))

    if any(x in texto_n for x in ["em estoque", "disponivel", "disponível", "in stock"]):
        return "1"

    return "1"


def _titulo_valido_para_admin(titulo: str) -> bool:
    titulo_n = normalizar_texto(titulo)
    if not titulo_n:
        return False

    bloqueados = {
        "produtos",
        "produto",
        "catalogo",
        "catálogo",
        "painel",
        "dashboard",
        "admin",
        "inicio",
        "home",
        "lista de produtos",
    }
    if titulo_n in bloqueados:
        return False

    if len(titulo_n) < 3:
        return False

    return True


def _texto_total_seguro(soup: BeautifulSoup) -> str:
    try:
        return safe_str(soup.get_text(" ", strip=True))
    except Exception:
        return ""


# ============================================================
# JSON-LD (MAIS FORTE)
# ============================================================

def extrair_json_ld(soup: BeautifulSoup) -> list[dict]:
    itens = []

    for script in soup.select("script[type='application/ld+json']"):
        bruto = safe_str(script.string or script.get_text(" ", strip=True))
        if not bruto:
            continue

        try:
            data = json.loads(bruto)
        except Exception:
            continue

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    itens.append(item)
        elif isinstance(data, dict):
            itens.append(data)

    return itens


def achatar_json_ld_produtos(itens: list[dict]) -> list[dict]:
    produtos = []

    def visitar(node: Any) -> None:
        if isinstance(node, dict):
            tipo = normalizar_texto(node.get("@type"))
            if "product" in tipo:
                produtos.append(node)

            for valor in node.values():
                visitar(valor)

        elif isinstance(node, list):
            for item in node:
                visitar(item)

    for item in itens:
        visitar(item)

    return produtos


def extrair_produto_json_ld(soup: BeautifulSoup, url_produto: str) -> dict:
    itens = extrair_json_ld(soup)
    produtos = achatar_json_ld_produtos(itens)

    if not produtos:
        return {}

    prod = produtos[0]

    nome = safe_str(prod.get("name"))
    sku = safe_str(prod.get("sku"))

    gtin = (
        safe_str(prod.get("gtin13"))
        or safe_str(prod.get("gtin14"))
        or safe_str(prod.get("gtin12"))
        or safe_str(prod.get("gtin8"))
        or safe_str(prod.get("gtin"))
    )
    gtin = _limpar_gtin(gtin)

    marca = ""
    brand = prod.get("brand")
    if isinstance(brand, dict):
        marca = safe_str(brand.get("name"))
    elif isinstance(brand, str):
        marca = brand

    categoria = safe_str(prod.get("category"))
    descricao = safe_str(prod.get("description"))

    imagens = prod.get("image", [])
    if isinstance(imagens, str):
        imagens = [imagens]

    imagens = [
        urljoin(url_produto, safe_str(img))
        for img in imagens
        if safe_str(img) and imagem_valida(urljoin(url_produto, safe_str(img)))
    ]

    preco = ""
    quantidade = ""

    offers = prod.get("offers")
    if isinstance(offers, dict):
        preco = safe_str(offers.get("price"))
        disponibilidade = normalizar_texto(offers.get("availability"))

        if "outofstock" in disponibilidade:
            quantidade = "0"
        else:
            quantidade = "1"

    return {
        "codigo": _limpar_codigo(sku),
        "descricao": nome,
        "descricao_detalhada": descricao,
        "descricao_curta": nome[:120] if nome else "",
        "categoria": categoria,
        "marca": marca,
        "gtin": gtin,
        "preco": normalizar_preco_para_planilha(preco),
        "quantidade": quantidade,
        "url_imagens": normalizar_imagens("|".join(imagens[:12])),
        "fonte_extracao": "json_ld",
    }


# ============================================================
# EXTRAÇÕES ESPECÍFICAS
# ============================================================

def extrair_marca(texto: str, soup: BeautifulSoup) -> str:
    marca = texto_por_selectors(
        soup,
        [
            "meta[property='og:brand']",
            "meta[name='brand']",
            "[itemprop='brand']",
            "[class*='brand']",
            "[class*='marca']",
            "[data-brand]",
        ],
    )

    if marca:
        return safe_str(marca)

    texto_total = safe_str(texto)

    match = re.search(r"(?:marca|brand)[\s:\-]*([A-Za-z0-9Á-ú .\-]{2,60})", texto_total, re.I)
    if match:
        return safe_str(match.group(1))

    return ""


def extrair_quantidade(texto: str) -> str:
    texto_n = normalizar_texto(texto)

    if any(x in texto_n for x in ["sem estoque", "indisponivel", "indisponível", "esgotado", "zerado", "outofstock"]):
        return "0"

    match = re.search(r"(?:estoque|quantidade|qtd)[^\d]{0,12}(\d{1,5})", texto_n, re.I)
    if match:
        return safe_str(match.group(1))

    if any(x in texto_n for x in ["em estoque", "disponivel", "disponível", "in stock"]):
        return "1"

    return ""


def extrair_breadcrumb(soup: BeautifulSoup) -> str:
    breadcrumb = []

    for el in soup.select("nav a, .breadcrumb a, [class*=breadcrumb] a, [aria-label*=breadcrumb] a"):
        txt = safe_str(el.get_text(" ", strip=True))
        txt_n = normalizar_texto(txt)
        if txt and txt_n not in {"home", "inicio"}:
            breadcrumb.append(txt)

    return " > ".join(dict.fromkeys(breadcrumb))


def extrair_codigo(texto: str, soup: BeautifulSoup) -> str:
    candidatos = [
        texto_por_selectors(
            soup,
            [
                "[itemprop='sku']",
                "[class*='sku']",
                "[class*='codigo']",
                "[class*='code']",
                "[data-sku]",
                "[data-code]",
                "meta[property='product:retailer_item_id']",
            ],
        ),
        _regex_busca(
            texto,
            [
                r"(?:sku|c[oó]digo|cod\.?|ref\.?)[\s:\-#]*([A-Za-z0-9._/\-]{3,60})",
                r"(?:ean|gtin)[\s:\-#]*([0-9]{8,14})",
            ],
        ),
    ]

    for candidato in candidatos:
        codigo = _limpar_codigo(candidato)
        if codigo:
            return codigo

    return ""


def extrair_gtin(texto: str, soup: BeautifulSoup) -> str:
    candidatos = [
        texto_por_selectors(
            soup,
            [
                "[itemprop='gtin13']",
                "[itemprop='gtin14']",
                "[itemprop='gtin12']",
                "[itemprop='gtin8']",
                "[class*='gtin']",
                "[class*='ean']",
                "[data-gtin]",
                "[data-ean]",
            ],
        ),
        _regex_busca(
            texto,
            [
                r"(?:gtin|ean)[\s:\-#]*([0-9]{8,14})",
                r"\b([0-9]{13})\b",
                r"\b([0-9]{14})\b",
                r"\b([0-9]{12})\b",
                r"\b([0-9]{8})\b",
            ],
        ),
    ]

    for candidato in candidatos:
        gtin = _limpar_gtin(candidato)
        if gtin:
            return gtin

    return ""


def extrair_ncm(texto: str, soup: BeautifulSoup) -> str:
    candidatos = [
        texto_por_selectors(
            soup,
            [
                "[class*='ncm']",
                "[data-ncm]",
            ],
        ),
        _regex_busca(
            texto,
            [
                r"(?:ncm)[\s:\-#]*([0-9.\-]{6,12})",
            ],
        ),
    ]

    for candidato in candidatos:
        valor = re.sub(r"\D+", "", safe_str(candidato))
        if len(valor) >= 6:
            return valor[:8]

    return ""


def extrair_descricao_admin_products(soup: BeautifulSoup, texto_total: str, json_ld: dict) -> str:
    candidatos = [
        texto_por_selectors(
            soup,
            [
                "h1",
                "[class*='product-title']",
                "[class*='produto-title']",
                "[class*='product_name']",
                "[class*='name']",
                "[itemprop='name']",
                "meta[property='og:title']",
                "title",
                "table tr td",
                "tbody tr td",
            ],
        ),
        json_ld.get("descricao", ""),
    ]

    for candidato in candidatos:
        titulo = safe_str(candidato)
        if _titulo_valido_para_admin(titulo):
            return titulo

    # fallback por regex em páginas administrativas/listagens
    linhas = [safe_str(x) for x in re.split(r"[\n\r]+", texto_total) if safe_str(x)]
    for linha in linhas:
        if _titulo_valido_para_admin(linha):
            if len(linha) > 5 and not re.fullmatch(r"[0-9.,\- ]+", linha):
                return linha[:180]

    return ""


def extrair_categoria_admin_products(soup: BeautifulSoup, texto_total: str, json_ld: dict) -> str:
    breadcrumb = extrair_breadcrumb(soup)
    if breadcrumb:
        return breadcrumb

    candidatos = [
        texto_por_selectors(
            soup,
            [
                "[class*='category']",
                "[class*='categoria']",
                "[data-category]",
            ],
        ),
        json_ld.get("categoria", ""),
        _regex_busca(
            texto_total,
            [
                r"(?:categoria|category)[\s:\-]*([A-Za-z0-9Á-ú \-_/]{3,80})",
            ],
        ),
    ]

    for candidato in candidatos:
        valor = safe_str(candidato)
        if valor and len(valor) >= 3:
            return valor[:120]

    return ""


# ============================================================
# EXTRAÇÃO PRINCIPAL
# ============================================================

def extrair_detalhes_heuristicos(url_produto: str, html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    texto_total = _texto_total_seguro(soup)
    cfg = fornecedor_cfg(url_produto)

    json_ld = extrair_produto_json_ld(soup, url_produto)

    titulo = extrair_descricao_admin_products(soup, texto_total, json_ld)
    if not titulo:
        titulo = texto_por_selectors(
            soup,
            [
                "h1",
                ".product-title",
                "[itemprop='name']",
                "meta[property='og:title']",
                "title",
            ],
        ) or json_ld.get("descricao", "")

    if not _titulo_valido_para_admin(titulo):
        titulo = json_ld.get("descricao", "") or titulo

    preco = texto_por_selectors(
        soup,
        [
            "[class*=price]",
            "[class*=preco]",
            "[itemprop='price']",
            "meta[property='product:price:amount']",
            "[data-price]",
        ],
    )
    if not preco:
        preco = extrair_preco(texto_total)

    preco = normalizar_preco_para_planilha(preco or json_ld.get("preco", ""))

    imagens = imagens_por_selectors(
        url_produto,
        soup,
        [
            "meta[property='og:image']",
            "[itemprop='image']",
            "[class*='gallery'] img",
            "[class*='image'] img",
            "[class*='foto'] img",
            "img",
            "a[href$='.jpg']",
            "a[href$='.jpeg']",
            "a[href$='.png']",
            "a[href$='.webp']",
        ],
    )

    if not imagens and json_ld.get("url_imagens"):
        imagens = [x for x in json_ld["url_imagens"].split("|") if safe_str(x)]

    imagens_filtradas = []
    vistos = set()
    for img in imagens:
        url_img = safe_str(img)
        if not url_img:
            continue
        if not imagem_valida(url_img):
            continue
        if not mesmo_dominio(url_produto, url_img) and "cdn" not in normalizar_texto(url_img):
            # deixa passar cdn, mas evita lixo externo
            continue
        if url_img in vistos:
            continue
        vistos.add(url_img)
        imagens_filtradas.append(url_img)

    marca = extrair_marca(texto_total, soup) or json_ld.get("marca", "")
    codigo = extrair_codigo(texto_total, soup) or json_ld.get("codigo", "")
    gtin = extrair_gtin(texto_total, soup) or json_ld.get("gtin", "")
    ncm = extrair_ncm(texto_total, soup)

    quantidade = extrair_quantidade(texto_total) or json_ld.get("quantidade", "")
    quantidade = _normalizar_quantidade(texto_total, quantidade_atual=quantidade)

    descricao_detalhada = (
        json_ld.get("descricao_detalhada", "")
        or texto_por_selectors(
            soup,
            [
                "[class*=description]",
                "[class*=descricao]",
                "[itemprop='description']",
                "meta[name='description']",
            ],
        )
    )

    descricao_detalhada = descricao_detalhada_valida(descricao_detalhada, titulo)

    categoria = extrair_categoria_admin_products(soup, texto_total, json_ld)

    # heurística extra para admin/products ou grids internos
    url_n = normalizar_texto(url_produto)
    if "/admin/products" in url_n and not codigo:
        codigo = _regex_busca(
            texto_total,
            [
                r"\bsku[\s:\-#]*([A-Za-z0-9._/\-]{3,60})",
                r"\bc[oó]digo[\s:\-#]*([A-Za-z0-9._/\-]{3,60})",
            ],
        )

    return {
        "url_produto": url_produto,
        "codigo": _limpar_codigo(codigo),
        "descricao": safe_str(titulo),
        "descricao_curta": safe_str(titulo)[:120],
        "descricao_detalhada": descricao_detalhada,
        "categoria": safe_str(categoria),
        "marca": safe_str(marca),
        "gtin": _limpar_gtin(gtin),
        "ncm": safe_str(ncm),
        "preco": preco,
        "quantidade": quantidade or "1",
        "url_imagens": normalizar_imagens("|".join(imagens_filtradas[:10])),
        "fonte_extracao": json_ld.get("fonte_extracao", "heuristica"),
        "cfg_fornecedor_detectada": safe_str(cfg.get("nome") or cfg.get("slug") or ""),
    }
