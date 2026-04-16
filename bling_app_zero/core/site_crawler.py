
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable
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


# ============================================================
# HELPERS BÁSICOS
# ============================================================

def _safe_str(valor) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"none", "nan", "nat"}:
        return ""
    return texto


def _normalizar_texto(valor: str) -> str:
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
    }
    for origem, destino in trocas.items():
        texto = texto.replace(origem, destino)
    return " ".join(texto.split())


def _headers() -> dict:
    return {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }


def _baixar_html(url: str) -> str:
    resposta = requests.get(url, headers=_headers(), timeout=TIMEOUT)
    resposta.raise_for_status()
    resposta.encoding = resposta.encoding or "utf-8"
    return resposta.text


def _soup(url: str) -> BeautifulSoup:
    return BeautifulSoup(_baixar_html(url), "html.parser")


def _url_mesmo_dominio(url_base: str, url_teste: str) -> bool:
    try:
        dom_base = urlparse(url_base).netloc.replace("www.", "")
        dom_teste = urlparse(url_teste).netloc.replace("www.", "")
        return dom_base == dom_teste
    except Exception:
        return False


def _deduplicar_ordem(seq: Iterable[str]) -> list[str]:
    vistos = set()
    saida = []
    for item in seq:
        chave = _safe_str(item)
        if not chave or chave in vistos:
            continue
        vistos.add(chave)
        saida.append(chave)
    return saida


def _to_float_brasil(valor) -> float:
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


def _formatar_numero_bling(valor) -> str:
    return f"{_to_float_brasil(valor):.2f}".replace(".", ",")


# ============================================================
# EXTRAÇÃO DE PREÇO / GTIN / IMAGENS
# ============================================================

def _extrair_jsonld(soup: BeautifulSoup) -> list[dict]:
    itens = []
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
            ".price-current",
            ".valor",
        ],
    )
    if texto_preco:
        encontrado = re.search(r"R\$\s*([\d\.\,]+)", texto_preco)
        if encontrado:
            return _formatar_numero_bling(encontrado.group(1))
        if _to_float_brasil(texto_preco) > 0:
            return _formatar_numero_bling(texto_preco)

    html_texto = soup.get_text(" ", strip=True)
    encontrado = re.search(r"R\$\s*([\d\.\,]+)", html_texto)
    if encontrado:
        return _formatar_numero_bling(encontrado.group(1))

    return ""


def _extrair_gtin(soup: BeautifulSoup, jsonlds: list[dict]) -> str:
    for item in jsonlds:
        for chave in ["gtin13", "gtin12", "gtin14", "gtin8", "gtin", "sku"]:
            valor = _safe_str(item.get(chave))
            if valor and re.fullmatch(r"[\d\- ]{8,20}", valor):
                return re.sub(r"\D", "", valor)

    html_texto = soup.get_text(" ", strip=True)
    for padrao in [
        r"(?:codigo|c[oó]digo|gtin|ean)\s*[:#]?\s*([0-9]{8,14})",
        r"\b([0-9]{8,14})\b",
    ]:
        encontrado = re.search(padrao, html_texto, re.IGNORECASE)
        if encontrado:
            return re.sub(r"\D", "", encontrado.group(1))

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
        urljoin(url_produto, i)
        for i in imagens
        if i and not any(bad in i.lower() for bad in ["icon", "logo", "sprite", "base64"])
    ]
    imagens = _deduplicar_ordem(imagens[:10])
    return "|".join(imagens)


# ============================================================
# EXTRAÇÃO DE NOME / CATEGORIA / DESCRIÇÃO
# ============================================================

def _extrair_nome(soup: BeautifulSoup, jsonlds: list[dict]) -> str:
    for item in jsonlds:
        nome = _safe_str(item.get("name"))
        if nome:
            return nome

    for seletor in [
        "h1",
        ".product-title",
        ".nome-produto",
        ".product-name",
        '[itemprop="name"]',
    ]:
        try:
            el = soup.select_one(seletor)
            if el:
                texto = _safe_str(el.get_text(" ", strip=True))
                if texto:
                    return texto
        except Exception:
            continue
    return ""


def _extrair_descricao_longa(soup: BeautifulSoup, jsonlds: list[dict]) -> str:
    for item in jsonlds:
        descricao = _safe_str(item.get("description"))
        if descricao:
            return descricao

    for seletor in [
        ".product-description",
        ".descricao",
        ".description",
        '[itemprop="description"]',
        ".tabs-description",
    ]:
        try:
            el = soup.select_one(seletor)
            if el:
                texto = _safe_str(el.get_text(" ", strip=True))
                if texto:
                    return texto
        except Exception:
            continue
    return ""


def _extrair_categoria(soup: BeautifulSoup) -> str:
    breadcrumbs = []
    for seletor in [
        ".breadcrumb a",
        ".breadcrumbs a",
        '[aria-label="breadcrumb"] a',
    ]:
        els = soup.select(seletor)
        if els:
            breadcrumbs = [_safe_str(x.get_text(" ", strip=True)) for x in els]
            breadcrumbs = [x for x in breadcrumbs if x]
            if breadcrumbs:
                break

    if breadcrumbs:
        return " > ".join(breadcrumbs)

    return ""


# ============================================================
# EXTRAÇÃO DE ESTOQUE REAL
# ============================================================

def _extrair_quantidade_numerica_direta(texto: str) -> int | None:
    padroes = [
        r"(\d+)\s*(?:unidades|unidade|itens|item)\s*(?:em estoque|disponiveis|disponíveis)",
        r"estoque\s*[:\-]?\s*(\d+)",
        r"quantidade\s*disponivel\s*[:\-]?\s*(\d+)",
        r"restam\s*(\d+)",
        r"apenas\s*(\d+)\s*(?:unidades|itens)",
        r"(\d+)\s*(?:produtos|unidades)\s*disponiveis",
    ]
    for padrao in padroes:
        encontrado = re.search(padrao, texto, re.IGNORECASE)
        if encontrado:
            try:
                return int(encontrado.group(1))
            except Exception:
                continue
    return None


def _extrair_quantidade_json(soup: BeautifulSoup, jsonlds: list[dict]) -> int | None:
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

            disponibilidade = _safe_str(offers.get("availability"))
            if "outofstock" in disponibilidade.lower():
                return 0

    for script in soup.find_all("script"):
        bruto = _safe_str(script.string or script.get_text(" ", strip=True))
        if not bruto:
            continue

        encontrado = re.search(r'"inventoryLevel"\s*:\s*\{[^}]*"value"\s*:\s*"?(\\d+)"?\}', bruto)
        if encontrado:
            try:
                return int(encontrado.group(1))
            except Exception:
                pass

        encontrado2 = re.search(r'"stock"\s*:\s*"?(\\d+)"?', bruto)
        if encontrado2:
            try:
                return int(encontrado2.group(1))
            except Exception:
                pass

    return None


def _inferir_quantidade_por_status(texto_normalizado: str, padrao_disponivel: int) -> int:
    if any(x in texto_normalizado for x in ["sem estoque", "esgotado", "indisponivel", "indisponível", "zerado"]):
        return 0

    if any(x in texto_normalizado for x in ["ultimas unidades", "últimas unidades", "ultimas pecas", "últimas peças"]):
        return 3

    if any(x in texto_normalizado for x in ["em estoque", "disponivel", "disponível", "a pronta entrega"]):
        return int(padrao_disponivel)

    return int(padrao_disponivel)


def _extrair_quantidade_real(soup: BeautifulSoup, jsonlds: list[dict], padrao_disponivel: int) -> int:
    quantidade_json = _extrair_quantidade_json(soup, jsonlds)
    if quantidade_json is not None:
        return max(int(quantidade_json), 0)

    texto_pagina = soup.get_text(" ", strip=True)
    quantidade_direta = _extrair_quantidade_numerica_direta(texto_pagina)
    if quantidade_direta is not None:
        return max(int(quantidade_direta), 0)

    texto_normalizado = _normalizar_texto(texto_pagina)
    return _inferir_quantidade_por_status(texto_normalizado, padrao_disponivel)


# ============================================================
# DETECÇÃO DE LINKS DE PRODUTO
# ============================================================

def _pontuar_link_produto(url: str, texto_link: str) -> int:
    url_n = _normalizar_texto(url)
    txt_n = _normalizar_texto(texto_link)
    score = 0

    if "/produto/" in url_n or "/product/" in url_n:
        score += 8
    if any(p in url_n for p in ["sku", "p-", "/p/"]):
        score += 4
    if len(txt_n.split()) >= 3:
        score += 2
    if any(x in txt_n for x in ["comprar", "ver detalhes", "detalhes"]):
        score += 1
    if re.search(r"/\d{5,}", url_n):
        score += 3
    return score


def _coletar_links_produto(url_categoria: str, max_paginas: int = 5) -> list[str]:
    links_encontrados: list[str] = []
    paginas_para_ler = [url_categoria]

    for pagina_url in paginas_para_ler[:max_paginas]:
        try:
            soup = _soup(pagina_url)
        except Exception:
            continue

        pagina_links = []
        for a in soup.find_all("a", href=True):
            href = urljoin(pagina_url, a.get("href"))
            texto = _safe_str(a.get_text(" ", strip=True))
            if not _url_mesmo_dominio(url_categoria, href):
                continue
            if _pontuar_link_produto(href, texto) >= 5:
                pagina_links.append(href)

        links_encontrados.extend(pagina_links)

        # Tentativa simples de paginação
        for a in soup.find_all("a", href=True):
            href = urljoin(pagina_url, a.get("href"))
            texto = _normalizar_texto(a.get_text(" ", strip=True))
            if not _url_mesmo_dominio(url_categoria, href):
                continue
            if any(x in texto for x in ["proxima", "próxima", "next"]) or "page=" in href.lower():
                if href not in paginas_para_ler and len(paginas_para_ler) < max_paginas:
                    paginas_para_ler.append(href)

    return _deduplicar_ordem(links_encontrados)


# ============================================================
# EXTRAÇÃO DE PRODUTO
# ============================================================

def _extrair_produto(url_produto: str, padrao_disponivel: int) -> dict:
    try:
        soup = _soup(url_produto)
        jsonlds = _extrair_jsonld(soup)

        nome = _extrair_nome(soup, jsonlds)
        descricao_longa = _extrair_descricao_longa(soup, jsonlds)
        categoria = _extrair_categoria(soup)
        preco = _extrair_preco(soup, jsonlds)
        gtin = _extrair_gtin(soup, jsonlds)
        imagens = _extrair_imagens(soup, url_produto, jsonlds)
        quantidade = _extrair_quantidade_real(soup, jsonlds, padrao_disponivel)

        return {
            "codigo_fornecedor": gtin,
            "descricao_fornecedor": nome,
            "descricao_longa": descricao_longa,
            "preco_base": preco,
            "quantidade_real": quantidade,
            "categoria": categoria,
            "url_imagens": imagens,
            "link_produto": url_produto,
        }
    except Exception:
        return {
            "codigo_fornecedor": "",
            "descricao_fornecedor": "",
            "descricao_longa": "",
            "preco_base": "",
            "quantidade_real": 0,
            "categoria": "",
            "url_imagens": "",
            "link_produto": url_produto,
        }


# ============================================================
# API PRINCIPAL
# ============================================================

def executar_crawler_site(
    url: str,
    max_paginas: int = 5,
    max_threads: int = 5,
    padrao_disponivel: int = 10,
) -> pd.DataFrame:
    url = _safe_str(url)
    if not url:
        return pd.DataFrame()

    max_paginas = max(1, int(max_paginas))
    max_threads = max(1, min(int(max_threads), 10))
    padrao_disponivel = max(0, int(padrao_disponivel))

    links = _coletar_links_produto(url, max_paginas=max_paginas)
    if not links:
        # tenta interpretar a própria URL como produto
        links = [url]

    produtos: list[dict] = []
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futuros = {
            executor.submit(_extrair_produto, link, padrao_disponivel): link
            for link in links
        }
        for futuro in as_completed(futuros):
            resultado = futuro.result()
            if _safe_str(resultado.get("descricao_fornecedor")):
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
        df["quantidade_real"] = pd.to_numeric(df["quantidade_real"], errors="coerce").fillna(0).astype(int)

    return df.reset_index(drop=True)
