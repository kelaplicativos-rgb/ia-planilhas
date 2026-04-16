
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

TIMEOUT = 20
BASE_URL = "https://www.atacadum.com.br/"


# ============================================================
# HELPERS BÁSICOS
# ============================================================

def _safe_str(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"none", "nan", "nat"}:
        return ""
    return texto


def _normalizar_texto(valor: Any) -> str:
    texto = _safe_str(valor).lower()
    trocas = {
        "ã": "a",
        "á": "a",
        "à": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
        "\xa0": " ",
        "_": " ",
        "-": " ",
    }
    for origem, destino in trocas.items():
        texto = texto.replace(origem, destino)
    return " ".join(texto.split())


def _headers() -> dict[str, str]:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def _baixar_html(url: str) -> str:
    resp = requests.get(url, headers=_headers(), timeout=TIMEOUT)
    resp.raise_for_status()
    resp.encoding = resp.encoding or "utf-8"
    return resp.text


def _soup(url: str) -> BeautifulSoup:
    return BeautifulSoup(_baixar_html(url), "html.parser")


def _url_mesmo_dominio(url_a: str, url_b: str) -> bool:
    try:
        dom_a = urlparse(url_a).netloc.replace("www.", "")
        dom_b = urlparse(url_b).netloc.replace("www.", "")
        return dom_a == dom_b
    except Exception:
        return False


def _deduplicar_ordem(valores: Iterable[str]) -> list[str]:
    vistos = set()
    saida: list[str] = []
    for valor in valores:
        texto = _safe_str(valor)
        if not texto or texto in vistos:
            continue
        vistos.add(texto)
        saida.append(texto)
    return saida


def _to_float_brasil(valor: Any) -> float:
    texto = _safe_str(valor)
    if not texto:
        return 0.0

    texto = texto.replace("R$", "").replace(" ", "")
    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        texto = texto.replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return 0.0


def _formatar_numero_bling(valor: Any) -> str:
    return f"{_to_float_brasil(valor):.2f}".replace(".", ",")


# ============================================================
# CATEGORIAS / LISTAS
# ============================================================

def _urls_seed_atacadum(categoria: str = "") -> list[str]:
    categoria = _normalizar_texto(categoria)

    seeds_fixas = [
        BASE_URL,
        urljoin(BASE_URL, "mais-produtos/"),
        urljoin(BASE_URL, "ofertas/"),
        urljoin(BASE_URL, "relogio-smartwatch/"),
        urljoin(BASE_URL, "camera/"),
        urljoin(BASE_URL, "gamer/"),
        urljoin(BASE_URL, "fones/"),
        urljoin(BASE_URL, "dia-a-dia/"),
        urljoin(BASE_URL, "perfumes/"),
    ]

    if categoria:
        slug = categoria.replace(" ", "-")
        seeds_fixas.insert(0, urljoin(BASE_URL, f"{slug}/"))

    return _deduplicar_ordem(seeds_fixas)


def _pontuar_link_produto(url: str, texto_link: str) -> int:
    url_n = _normalizar_texto(url)
    txt_n = _normalizar_texto(texto_link)
    score = 0

    if "/produto/" in url_n or "/product/" in url_n:
        score += 8
    if "/p/" in url_n or "sku" in url_n:
        score += 4
    if re.search(r"/\d{5,}", url_n):
        score += 3
    if len(txt_n.split()) >= 3:
        score += 2
    return score


def _coletar_links_produto_lista(url_lista: str, max_paginas: int = 6) -> list[str]:
    links_produtos: list[str] = []
    paginas = [url_lista]

    for pagina in paginas[:max_paginas]:
        try:
            soup = _soup(pagina)
        except Exception:
            continue

        pagina_links = []
        for a in soup.find_all("a", href=True):
            href = urljoin(pagina, a.get("href"))
            texto = _safe_str(a.get_text(" ", strip=True))
            if not _url_mesmo_dominio(url_lista, href):
                continue
            if _pontuar_link_produto(href, texto) >= 5:
                pagina_links.append(href)
        links_produtos.extend(pagina_links)

        for a in soup.find_all("a", href=True):
            href = urljoin(pagina, a.get("href"))
            texto = _normalizar_texto(a.get_text(" ", strip=True))
            if not _url_mesmo_dominio(url_lista, href):
                continue
            if any(x in texto for x in ["proxima", "próxima", "next"]) or "page=" in href.lower():
                if href not in paginas and len(paginas) < max_paginas:
                    paginas.append(href)

    return _deduplicar_ordem(links_produtos)


# ============================================================
# EXTRAÇÃO DE PRODUTO
# ============================================================

def _extrair_jsonld(soup: BeautifulSoup) -> list[dict]:
    itens: list[dict] = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        bruto = _safe_str(tag.string or tag.get_text(" ", strip=True))
        if not bruto:
            continue
        try:
            dado = json.loads(bruto)
            if isinstance(dado, list):
                itens.extend([x for x in dado if isinstance(x, dict)])
            elif isinstance(dado, dict):
                itens.append(dado)
        except Exception:
            continue
    return itens


def _buscar_primeiro_texto(soup: BeautifulSoup, seletores: list[str]) -> str:
    for seletor in seletores:
        try:
            el = soup.select_one(seletor)
            if el:
                texto = _safe_str(el.get_text(" ", strip=True))
                if texto:
                    return texto
        except Exception:
            continue
    return ""


def _buscar_primeiro_atributo(soup: BeautifulSoup, seletores: list[tuple[str, str]]) -> str:
    for seletor, atributo in seletores:
        try:
            el = soup.select_one(seletor)
            if el:
                valor = _safe_str(el.get(atributo))
                if valor:
                    return valor
        except Exception:
            continue
    return ""


def _extrair_nome(soup: BeautifulSoup, jsonlds: list[dict]) -> str:
    for item in jsonlds:
        nome = _safe_str(item.get("name"))
        if nome:
            return nome

    return _buscar_primeiro_texto(
        soup,
        [
            "h1",
            ".product-title",
            ".product-name",
            ".nome-produto",
            '[itemprop="name"]',
        ],
    )


def _extrair_descricao(soup: BeautifulSoup, jsonlds: list[dict]) -> str:
    for item in jsonlds:
        descricao = _safe_str(item.get("description"))
        if descricao:
            return descricao

    return _buscar_primeiro_texto(
        soup,
        [
            ".product-description",
            ".descricao",
            ".description",
            '[itemprop="description"]',
            ".tabs-description",
        ],
    )


def _extrair_preco(soup: BeautifulSoup, jsonlds: list[dict]) -> str:
    for item in jsonlds:
        offers = item.get("offers")
        if isinstance(offers, dict):
            preco = offers.get("price") or offers.get("lowPrice")
            if _to_float_brasil(preco) > 0:
                return _formatar_numero_bling(preco)

    meta_preco = _buscar_primeiro_atributo(
        soup,
        [
            ('meta[itemprop="price"]', "content"),
            ('meta[property="product:price:amount"]', "content"),
            ('meta[name="twitter:data1"]', "content"),
        ],
    )
    if _to_float_brasil(meta_preco) > 0:
        return _formatar_numero_bling(meta_preco)

    texto_preco = _buscar_primeiro_texto(
        soup,
        [
            '[itemprop="price"]',
            ".price",
            ".preco",
            ".product-price",
            ".preco-por",
            ".valor",
        ],
    )
    if texto_preco:
        achado = re.search(r"R\$\s*([\d\.\,]+)", texto_preco)
        if achado:
            return _formatar_numero_bling(achado.group(1))
        if _to_float_brasil(texto_preco) > 0:
            return _formatar_numero_bling(texto_preco)

    html_texto = soup.get_text(" ", strip=True)
    achado = re.search(r"R\$\s*([\d\.\,]+)", html_texto)
    if achado:
        return _formatar_numero_bling(achado.group(1))

    return ""


def _extrair_codigo(soup: BeautifulSoup, jsonlds: list[dict], url_produto: str) -> str:
    for item in jsonlds:
        for chave in ["sku", "productID", "mpn", "gtin13", "gtin", "gtin12", "gtin14", "gtin8"]:
            valor = _safe_str(item.get(chave))
            if valor:
                return re.sub(r"\s+", "", valor)

    html_texto = soup.get_text(" ", strip=True)
    padroes = [
        r"(?:codigo|c[oó]digo|sku|ref)\s*[:#]?\s*([A-Za-z0-9\-_\.]{4,})",
        r"\b([0-9]{8,14})\b",
    ]
    for padrao in padroes:
        encontrado = re.search(padrao, html_texto, re.IGNORECASE)
        if encontrado:
            return _safe_str(encontrado.group(1))

    slug = urlparse(url_produto).path.strip("/").split("/")[-1]
    return _safe_str(slug)[:60]


def _extrair_gtin(soup: BeautifulSoup, jsonlds: list[dict]) -> str:
    for item in jsonlds:
        for chave in ["gtin13", "gtin12", "gtin14", "gtin8", "gtin"]:
            valor = _safe_str(item.get(chave))
            numeros = re.sub(r"\D", "", valor)
            if len(numeros) in {8, 12, 13, 14}:
                return numeros

    html_texto = soup.get_text(" ", strip=True)
    encontrado = re.search(r"(?:gtin|ean|codigo de barras)\s*[:#]?\s*([0-9]{8,14})", html_texto, re.IGNORECASE)
    if encontrado:
        return encontrado.group(1)

    return ""


def _extrair_categoria(soup: BeautifulSoup) -> str:
    for seletor in [
        ".breadcrumb a",
        ".breadcrumbs a",
        '[aria-label="breadcrumb"] a',
    ]:
        els = soup.select(seletor)
        if els:
            partes = [_safe_str(x.get_text(" ", strip=True)) for x in els]
            partes = [x for x in partes if x]
            if partes:
                return " > ".join(partes)
    return ""


def _extrair_imagens(soup: BeautifulSoup, url_produto: str, jsonlds: list[dict]) -> str:
    imagens: list[str] = []

    for item in jsonlds:
        valor = item.get("image")
        if isinstance(valor, list):
            imagens.extend([_safe_str(x) for x in valor if _safe_str(x)])
        elif isinstance(valor, str):
            imagens.append(valor)

    og_image = _buscar_primeiro_atributo(
        soup,
        [
            ('meta[property="og:image"]', "content"),
            ('meta[name="twitter:image"]', "content"),
        ],
    )
    if og_image:
        imagens.append(og_image)

    for img in soup.select("img"):
        src = _safe_str(img.get("src") or img.get("data-src") or img.get("data-lazy"))
        if not src:
            continue
        src = urljoin(url_produto, src)
        if _url_mesmo_dominio(url_produto, src):
            imagens.append(src)

    imagens = [
        urljoin(url_produto, img)
        for img in imagens
        if img and not any(bad in img.lower() for bad in ["icon", "logo", "sprite", "base64"])
    ]
    imagens = _deduplicar_ordem(imagens[:10])
    return "|".join(imagens)


def _extrair_quantidade_real(soup: BeautifulSoup, jsonlds: list[dict]) -> int:
    for item in jsonlds:
        offers = item.get("offers")
        if isinstance(offers, dict):
            quantidade = offers.get("inventoryLevel")
            if isinstance(quantidade, dict):
                valor = quantidade.get("value")
                if str(valor).isdigit():
                    return int(valor)
            if isinstance(quantidade, (int, float, str)) and str(quantidade).isdigit():
                return int(quantidade)

            disponibilidade = _safe_str(offers.get("availability")).lower()
            if "outofstock" in disponibilidade:
                return 0
            if "instock" in disponibilidade:
                return 10

    html_texto = _normalizar_texto(soup.get_text(" ", strip=True))

    if any(x in html_texto for x in ["sem estoque", "esgotado", "indisponivel", "indisponível", "zerado"]):
        return 0
    if any(x in html_texto for x in ["ultimas unidades", "últimas unidades", "ultimas pecas", "últimas peças"]):
        return 3
    if any(x in html_texto for x in ["em estoque", "disponivel", "disponível", "a pronta entrega"]):
        return 10

    return 10


def _extrair_produto_atacadum(url_produto: str) -> dict:
    try:
        soup = _soup(url_produto)
        jsonlds = _extrair_jsonld(soup)

        nome = _extrair_nome(soup, jsonlds)
        if not nome:
            return {}

        return {
            "codigo_fornecedor": _extrair_codigo(soup, jsonlds, url_produto),
            "descricao_fornecedor": nome,
            "descricao_longa": _extrair_descricao(soup, jsonlds),
            "preco_base": _extrair_preco(soup, jsonlds),
            "quantidade_real": _extrair_quantidade_real(soup, jsonlds),
            "gtin": _extrair_gtin(soup, jsonlds),
            "categoria": _extrair_categoria(soup),
            "url_imagens": _extrair_imagens(soup, url_produto, jsonlds),
            "link_produto": url_produto,
        }
    except Exception:
        return {}


# ============================================================
# API PRINCIPAL
# ============================================================

def buscar_produtos_atacadum(
    fornecedor: str = "atacadum",
    categoria: str = "",
    operacao: str = "",
    config: dict | None = None,
) -> pd.DataFrame:
    _ = fornecedor, operacao  # mantidos para compatibilidade

    if isinstance(config, dict):
        categoria = _safe_str(config.get("categoria")) or categoria

    seeds = _urls_seed_atacadum(categoria=categoria)

    links: list[str] = []
    for seed in seeds:
        try:
            links.extend(_coletar_links_produto_lista(seed, max_paginas=6))
        except Exception:
            continue

    links = _deduplicar_ordem(links)
    if not links:
        return pd.DataFrame()

    produtos: list[dict] = []
    with ThreadPoolExecutor(max_workers=6) as executor:
        futuros = {executor.submit(_extrair_produto_atacadum, link): link for link in links}
        for futuro in as_completed(futuros):
            resultado = futuro.result()
            if resultado and _safe_str(resultado.get("descricao_fornecedor")):
                produtos.append(resultado)

    if not produtos:
        return pd.DataFrame()

    df = pd.DataFrame(produtos).fillna("")

    if "link_produto" in df.columns:
        df = df.drop_duplicates(subset=["link_produto"], keep="first")
    else:
        df = df.drop_duplicates(subset=["descricao_fornecedor"], keep="first")

    if "preco_base" in df.columns:
        df["preco_base"] = df["preco_base"].apply(_formatar_numero_bling)

    if "quantidade_real" in df.columns:
        df["quantidade_real"] = pd.to_numeric(
            df["quantidade_real"], errors="coerce"
        ).fillna(0).astype(int)

    colunas_finais = [
        "codigo_fornecedor",
        "descricao_fornecedor",
        "descricao_longa",
        "preco_base",
        "quantidade_real",
        "gtin",
        "categoria",
        "url_imagens",
        "link_produto",
    ]

    for coluna in colunas_finais:
        if coluna not in df.columns:
            df[coluna] = ""

    return df[colunas_finais].reset_index(drop=True)
