from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from bling_app_zero.core.site_crawler_cleaners import (
    descricao_detalhada_valida,
    extrair_preco,
    fornecedor_cfg,
    imagem_valida,
    limpar_codigo,
    limpar_gtin,
    limpar_marca,
    limpar_texto_produto,
    mesmo_dominio,
    normalizar_imagens,
    normalizar_preco_para_planilha,
    normalizar_texto,
    safe_str,
    titulo_produto_valido,
)

try:
    from bling_app_zero.core.site_supplier_profiles import get_supplier_profile
except Exception:
    def get_supplier_profile(url: str):
        return None


TITLE_SELECTORS_FORTES = [
    "meta[property='og:title']",
    "meta[name='twitter:title']",
    "[itemprop='name']",
    "h1",
    "[class*='product-title']",
    "[class*='produto-title']",
    ".product_title",
    ".product-name",
    ".entry-title",
]

PRICE_SELECTORS_FORTES = [
    "meta[property='product:price:amount']",
    "[itemprop='price']",
    "[data-price]",
    "[class*='price']",
    "[class*='preco']",
]

DESCRIPTION_SELECTORS_FORTES = [
    "[itemprop='description']",
    "meta[name='description']",
    "meta[property='og:description']",
    "[class*='description']",
    "[class*='descricao']",
    "[id*='description']",
    "[id*='descricao']",
]

IMAGE_SELECTORS_FORTES = [
    "meta[property='og:image']",
    "meta[name='twitter:image']",
    "[itemprop='image']",
    "[class*='gallery'] img",
    "[class*='image'] img",
    "[class*='foto'] img",
    "img[src]",
    "img[data-src]",
    "img[data-lazy-src]",
    "a[href$='.jpg']",
    "a[href$='.jpeg']",
    "a[href$='.png']",
    "a[href$='.webp']",
]

CODE_PATTERNS = [
    r"(?:sku|c[oó]digo|codigo|ref\.?|refer[eê]ncia)[\s:\-#]*([A-Za-z0-9._/\-]{3,60})",
    r'"sku"\s*:\s*"([^"]{3,60})"',
    r'"productid"\s*:\s*"([^"]{3,60})"',
    r'"product_id"\s*:\s*"([^"]{3,60})"',
    r'"reference"\s*:\s*"([^"]{3,60})"',
]

GTIN_PATTERNS = [
    r"(?:gtin|ean)[\s:\-#]*([0-9]{8,14})",
    r'"gtin(?:8|12|13|14)?"\s*:\s*"([0-9]{8,14})"',
    r"\b([0-9]{13})\b",
    r"\b([0-9]{14})\b",
    r"\b([0-9]{12})\b",
    r"\b([0-9]{8})\b",
]

NCM_PATTERNS = [
    r"(?:ncm)[\s:\-#]*([0-9.\-]{6,12})",
]


def _profile(url: str):
    try:
        return get_supplier_profile(url)
    except Exception:
        return None


def _texto_meta_ou_elemento(el) -> str:
    if not el:
        return ""
    if getattr(el, "name", "") == "meta":
        return safe_str(el.get("content"))
    return safe_str(el.get_text(" ", strip=True))


def _valor_rank_score(valor: str, campo: str) -> int:
    texto = safe_str(valor)
    if not texto:
        return -999

    score = len(texto)
    texto_n = normalizar_texto(texto)

    if campo in {"descricao", "descricao_detalhada"}:
        if "entrando" in texto_n or "loading" in texto_n or "carregando" in texto_n:
            score -= 200
        if len(texto) >= 20:
            score += 40
        if len(texto) >= 50:
            score += 30

    if campo == "categoria" and ">" in texto:
        score += 60

    if campo == "preco" and re.search(r"\d", texto):
        score += 40

    if campo == "codigo":
        if re.search(r"\d", texto):
            score += 30
        if "-" in texto or "_" in texto or "." in texto or "/" in texto:
            score += 5

    return score


def _melhor_candidato(candidatos: list[tuple[int, str]], campo: str) -> str:
    if not candidatos:
        return ""

    candidatos = [(fonte, safe_str(valor)) for fonte, valor in candidatos if safe_str(valor)]
    if not candidatos:
        return ""

    melhor = ""
    melhor_score = -99999

    for fonte_score, valor in candidatos:
        score = fonte_score + _valor_rank_score(valor, campo)
        if score > melhor_score:
            melhor = valor
            melhor_score = score

    return melhor


def texto_por_selectors(soup: BeautifulSoup, selectors: list[str]) -> str:
    candidatos: list[tuple[int, str]] = []

    for idx, selector in enumerate(selectors):
        try:
            el = soup.select_one(selector)
        except Exception:
            el = None

        if not el:
            continue

        valor = _texto_meta_ou_elemento(el)
        if valor:
            candidatos.append((100 - idx, valor))

    return _melhor_candidato(candidatos, "descricao")


def imagens_por_selectors(url_produto: str, soup: BeautifulSoup, selectors: list[str]) -> list[str]:
    imagens = []
    vistos = set()

    for selector in selectors:
        try:
            elementos = soup.select(selector)
        except Exception:
            elementos = []

        for el in elementos:
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

    return imagens[:12]


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


def _texto_total_seguro(soup: BeautifulSoup) -> str:
    try:
        return safe_str(soup.get_text(" ", strip=True))
    except Exception:
        return ""


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


def _json_ld_score(prod: dict) -> int:
    score = 0
    if safe_str(prod.get("name")):
        score += 30
    if safe_str(prod.get("sku")):
        score += 20
    if safe_str(prod.get("description")):
        score += 10
    if safe_str(prod.get("category")):
        score += 8

    offers = prod.get("offers")
    if isinstance(offers, dict):
        if safe_str(offers.get("price")):
            score += 20
        if safe_str(offers.get("availability")):
            score += 5

    images = prod.get("image")
    if images:
        score += 7

    return score


def extrair_produto_json_ld(soup: BeautifulSoup, url_produto: str) -> dict:
    itens = extrair_json_ld(soup)
    produtos = achatar_json_ld_produtos(itens)

    if not produtos:
        return {}

    produtos.sort(key=_json_ld_score, reverse=True)
    prod = produtos[0]

    nome = limpar_texto_produto(prod.get("name"), max_len=220)
    sku = limpar_codigo(prod.get("sku"))

    gtin = (
        safe_str(prod.get("gtin13"))
        or safe_str(prod.get("gtin14"))
        or safe_str(prod.get("gtin12"))
        or safe_str(prod.get("gtin8"))
        or safe_str(prod.get("gtin"))
    )
    gtin = limpar_gtin(gtin)

    marca = ""
    brand = prod.get("brand")
    if isinstance(brand, dict):
        marca = limpar_marca(brand.get("name"))
    elif isinstance(brand, str):
        marca = limpar_marca(brand)

    categoria = limpar_texto_produto(prod.get("category"), max_len=120)
    descricao = descricao_detalhada_valida(prod.get("description", ""), nome)

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
        preco = normalizar_preco_para_planilha(safe_str(offers.get("price")))
        disponibilidade = normalizar_texto(offers.get("availability"))

        if "outofstock" in disponibilidade:
            quantidade = "0"
        elif disponibilidade:
            quantidade = "1"

    return {
        "codigo": sku,
        "descricao": nome,
        "descricao_detalhada": descricao,
        "descricao_curta": nome[:120] if nome else "",
        "categoria": categoria,
        "marca": marca,
        "gtin": gtin,
        "preco": preco,
        "quantidade": quantidade,
        "url_imagens": normalizar_imagens("|".join(imagens[:12])),
        "fonte_extracao": "json_ld",
    }


def extrair_marca(texto: str, soup: BeautifulSoup) -> str:
    candidatos: list[tuple[int, str]] = []

    for idx, selector in enumerate([
        "meta[property='og:brand']",
        "meta[name='brand']",
        "[itemprop='brand']",
        "[class*='brand']",
        "[class*='marca']",
        "[data-brand]",
    ]):
        try:
            el = soup.select_one(selector)
        except Exception:
            el = None
        if el:
            valor = limpar_marca(_texto_meta_ou_elemento(el))
            if valor:
                candidatos.append((100 - idx, valor))

    texto_total = safe_str(texto)
    match = re.search(r"(?:marca|brand)[\s:\-]*([A-Za-z0-9Á-ú .\-]{2,60})", texto_total, re.I)
    if match:
        valor = limpar_marca(match.group(1))
        if valor:
            candidatos.append((50, valor))

    return _melhor_candidato(candidatos, "marca")


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
        txt = limpar_texto_produto(el.get_text(" ", strip=True), max_len=80)
        txt_n = normalizar_texto(txt)
        if txt and txt_n not in {"home", "inicio", "início"}:
            breadcrumb.append(txt)

    if not breadcrumb:
        return ""

    return " > ".join(dict.fromkeys(breadcrumb))


def extrair_codigo(texto: str, soup: BeautifulSoup) -> str:
    candidatos: list[tuple[int, str]] = []

    seletores = [
        "[itemprop='sku']",
        "[class*='sku']",
        "[class*='codigo']",
        "[class*='code']",
        "[data-sku]",
        "[data-code]",
        "meta[property='product:retailer_item_id']",
    ]

    for idx, selector in enumerate(seletores):
        try:
            el = soup.select_one(selector)
        except Exception:
            el = None
        if not el:
            continue

        valor = limpar_codigo(_texto_meta_ou_elemento(el))
        if valor:
            candidatos.append((100 - idx, valor))

    valor_regex = limpar_codigo(_regex_busca(texto, CODE_PATTERNS))
    if valor_regex:
        candidatos.append((70, valor_regex))

    return _melhor_candidato(candidatos, "codigo")


def extrair_gtin(texto: str, soup: BeautifulSoup) -> str:
    candidatos: list[tuple[int, str]] = []

    seletores = [
        "[itemprop='gtin13']",
        "[itemprop='gtin14']",
        "[itemprop='gtin12']",
        "[itemprop='gtin8']",
        "[class*='gtin']",
        "[class*='ean']",
        "[data-gtin]",
        "[data-ean]",
    ]

    for idx, selector in enumerate(seletores):
        try:
            el = soup.select_one(selector)
        except Exception:
            el = None
        if not el:
            continue

        valor = limpar_gtin(_texto_meta_ou_elemento(el))
        if valor:
            candidatos.append((100 - idx, valor))

    valor_regex = limpar_gtin(_regex_busca(texto, GTIN_PATTERNS))
    if valor_regex:
        candidatos.append((70, valor_regex))

    return _melhor_candidato(candidatos, "gtin")


def extrair_ncm(texto: str, soup: BeautifulSoup) -> str:
    candidatos: list[tuple[int, str]] = []

    for idx, selector in enumerate([
        "[class*='ncm']",
        "[data-ncm]",
    ]):
        try:
            el = soup.select_one(selector)
        except Exception:
            el = None
        if not el:
            continue

        valor = re.sub(r"\D+", "", _texto_meta_ou_elemento(el))[:8]
        if len(valor) >= 6:
            candidatos.append((100 - idx, valor))

    valor_regex = re.sub(r"\D+", "", _regex_busca(texto, NCM_PATTERNS))[:8]
    if len(valor_regex) >= 6:
        candidatos.append((70, valor_regex))

    return _melhor_candidato(candidatos, "ncm")


def _categoria_por_url_produto(url_produto: str) -> str:
    profile = _profile(url_produto)
    path_parts = [p for p in urlparse(url_produto).path.split("/") if safe_str(p)]

    if not path_parts:
        return ""

    if profile is not None:
        category_hints = tuple(getattr(profile, "category_path_hints", ()) or ())
        for hint in category_hints:
            hint_n = safe_str(hint).strip("/").lower()
            if not hint_n:
                continue
            for idx, parte in enumerate(path_parts):
                if safe_str(parte).lower() == hint_n and idx + 1 < len(path_parts):
                    return limpar_texto_produto(safe_str(path_parts[idx + 1]).replace("-", " ").title(), max_len=120)

        category_keywords = tuple(getattr(profile, "category_url_keywords", ()) or ())
        keywords_n = {safe_str(x).lower() for x in category_keywords if safe_str(x)}
        for parte in path_parts:
            parte_n = safe_str(parte).lower()
            if parte_n in keywords_n:
                continue
            if parte_n not in {"produto", "produtos", "product", "products", "p", "item", "sku"} and len(parte_n) > 2:
                return limpar_texto_produto(safe_str(parte).replace("-", " ").title(), max_len=120)

    for parte in path_parts[:-1]:
        parte_n = safe_str(parte).lower()
        if parte_n not in {"produto", "produtos", "product", "products", "p", "item", "sku", "categoria", "categorias", "departamento"}:
            if len(parte_n) > 2:
                return limpar_texto_produto(safe_str(parte).replace("-", " ").title(), max_len=120)

    return ""


def extrair_categoria_admin_products(soup: BeautifulSoup, texto_total: str, json_ld: dict, url_produto: str = "") -> str:
    candidatos: list[tuple[int, str]] = []

    breadcrumb = extrair_breadcrumb(soup)
    if breadcrumb:
        candidatos.append((120, breadcrumb))

    for idx, selector in enumerate([
        "[class*='category']",
        "[class*='categoria']",
        "[data-category]",
    ]):
        try:
            el = soup.select_one(selector)
        except Exception:
            el = None
        if not el:
            continue

        valor = limpar_texto_produto(_texto_meta_ou_elemento(el), max_len=120)
        if valor:
            candidatos.append((100 - idx, valor))

    categoria_json = limpar_texto_produto(json_ld.get("categoria", ""), max_len=120)
    if categoria_json:
        candidatos.append((90, categoria_json))

    categoria_regex = limpar_texto_produto(
        _regex_busca(
            texto_total,
            [r"(?:categoria|category)[\s:\-]*([A-Za-z0-9Á-ú \-_/]{3,80})"],
        ),
        max_len=120,
    )
    if categoria_regex:
        candidatos.append((70, categoria_regex))

    if url_produto:
        categoria_url = _categoria_por_url_produto(url_produto)
        if categoria_url:
            candidatos.append((60, categoria_url))

    return _melhor_candidato(candidatos, "categoria")


def _filtrar_imagens(url_produto: str, imagens: list[str]) -> list[str]:
    imagens_filtradas = []
    vistos = set()

    for img in imagens:
        url_img = safe_str(img)
        if not url_img:
            continue
        if not imagem_valida(url_img):
            continue
        if not mesmo_dominio(url_produto, url_img) and "cdn" not in normalizar_texto(url_img):
            continue
        if url_img in vistos:
            continue
        vistos.add(url_img)
        imagens_filtradas.append(url_img)

    return imagens_filtradas[:12]


def _extrair_titulo_priorizado(soup: BeautifulSoup, texto_total: str, json_ld: dict) -> str:
    candidatos: list[tuple[int, str]] = []

    nome_json = limpar_texto_produto(json_ld.get("descricao", ""), max_len=220)
    if titulo_produto_valido(nome_json):
        candidatos.append((140, nome_json))

    for idx, selector in enumerate(TITLE_SELECTORS_FORTES):
        try:
            el = soup.select_one(selector)
        except Exception:
            el = None
        if not el:
            continue

        valor = limpar_texto_produto(_texto_meta_ou_elemento(el), max_len=220)
        if titulo_produto_valido(valor):
            candidatos.append((120 - idx, valor))

    linhas = [limpar_texto_produto(x, max_len=220) for x in re.split(r"[\n\r]+", texto_total)]
    for linha in linhas:
        if titulo_produto_valido(linha):
            candidatos.append((40, linha))
            break

    return _melhor_candidato(candidatos, "descricao")


def _extrair_preco_priorizado(soup: BeautifulSoup, texto_total: str, json_ld: dict) -> str:
    candidatos: list[tuple[int, str]] = []

    preco_json = normalizar_preco_para_planilha(json_ld.get("preco", ""))
    if preco_json:
        candidatos.append((140, preco_json))

    for idx, selector in enumerate(PRICE_SELECTORS_FORTES):
        try:
            el = soup.select_one(selector)
        except Exception:
            el = None
        if not el:
            continue

        valor = normalizar_preco_para_planilha(_texto_meta_ou_elemento(el))
        if valor:
            candidatos.append((120 - idx, valor))

    match_regex = extrair_preco(texto_total)
    valor_regex = normalizar_preco_para_planilha(match_regex)
    if valor_regex:
        candidatos.append((80, valor_regex))

    return _melhor_candidato(candidatos, "preco")


def _extrair_descricao_detalhada_priorizada(soup: BeautifulSoup, titulo: str, json_ld: dict) -> str:
    candidatos: list[tuple[int, str]] = []

    desc_json = descricao_detalhada_valida(json_ld.get("descricao_detalhada", ""), titulo)
    if desc_json:
        candidatos.append((140, desc_json))

    for idx, selector in enumerate(DESCRIPTION_SELECTORS_FORTES):
        try:
            el = soup.select_one(selector)
        except Exception:
            el = None
        if not el:
            continue

        valor = _texto_meta_ou_elemento(el)
        valor = descricao_detalhada_valida(valor, titulo)
        if valor:
            candidatos.append((120 - idx, valor))

    return _melhor_candidato(candidatos, "descricao_detalhada")


def extrair_detalhes_heuristicos(url_produto: str, html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    texto_total = _texto_total_seguro(soup)
    cfg = fornecedor_cfg(url_produto)

    json_ld = extrair_produto_json_ld(soup, url_produto)

    titulo = _extrair_titulo_priorizado(soup, texto_total, json_ld)
    preco = _extrair_preco_priorizado(soup, texto_total, json_ld)

    imagens = imagens_por_selectors(url_produto, soup, IMAGE_SELECTORS_FORTES)

    if not imagens and json_ld.get("url_imagens"):
        imagens = [x for x in safe_str(json_ld["url_imagens"]).split("|") if safe_str(x)]

    imagens_filtradas = _filtrar_imagens(url_produto, imagens)

    marca = extrair_marca(texto_total, soup) or limpar_marca(json_ld.get("marca", ""))
    codigo = extrair_codigo(texto_total, soup) or limpar_codigo(json_ld.get("codigo", ""))
    gtin = extrair_gtin(texto_total, soup) or limpar_gtin(json_ld.get("gtin", ""))
    ncm = extrair_ncm(texto_total, soup)

    quantidade = extrair_quantidade(texto_total) or safe_str(json_ld.get("quantidade", ""))
    quantidade = quantidade if quantidade in {"0", "1"} or safe_str(quantidade).isdigit() else ""

    descricao_detalhada = _extrair_descricao_detalhada_priorizada(soup, titulo, json_ld)
    categoria = extrair_categoria_admin_products(soup, texto_total, json_ld, url_produto=url_produto)

    url_n = normalizar_texto(url_produto)
    if "/admin/products" in url_n and not codigo:
        codigo = limpar_codigo(
            _regex_busca(
                texto_total,
                [
                    r"\bsku[\s:\-#]*([A-Za-z0-9._/\-]{3,60})",
                    r"\bc[oó]digo[\s:\-#]*([A-Za-z0-9._/\-]{3,60})",
                ],
            )
        )

    if not codigo:
        slug = safe_str(urlparse(url_produto).path.split("/")[-1])
        if slug and len(slug) >= 6 and slug.lower() not in {"produto", "product", "produtos", "products"}:
            codigo = limpar_codigo(slug[:60])

    titulo = limpar_texto_produto(titulo, max_len=220)
    categoria = limpar_texto_produto(categoria, max_len=120)
    marca = limpar_marca(marca)
    codigo = limpar_codigo(codigo)
    gtin = limpar_gtin(gtin)

    return {
        "url_produto": url_produto,
        "codigo": codigo,
        "descricao": titulo if titulo_produto_valido(titulo) else "",
        "descricao_curta": titulo[:120] if titulo_produto_valido(titulo) else "",
        "descricao_detalhada": descricao_detalhada,
        "categoria": categoria,
        "marca": marca,
        "gtin": gtin,
        "ncm": safe_str(ncm),
        "preco": preco,
        "quantidade": quantidade or "1",
        "url_imagens": normalizar_imagens("|".join(imagens_filtradas[:10])),
        "fonte_extracao": json_ld.get("fonte_extracao", "heuristica"),
        "cfg_fornecedor_detectada": safe_str(cfg.get("nome") or cfg.get("slug") or ""),
    }
