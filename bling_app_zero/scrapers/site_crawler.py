import posixpath
import re
import xml.etree.ElementTree as ET
from collections import deque
from typing import Dict, List, Set
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import pandas as pd
from bs4 import BeautifulSoup

from .ai_enriquecimento import enriquecer_produto_com_ia
from .extrator_produto import classificar_pagina, extrair_produto_html
from .fetcher import baixar_html

IGNORED_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".pdf",
    ".zip",
    ".rar",
    ".7z",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".csv",
)

PRODUCT_HINTS = (
    "/produto",
    "/product",
    "/produtos/",
    "/p/",
    "/pd-",
    "/item/",
    "/sku/",
    "/shop/",
)

CATEGORY_HINTS = (
    "/categoria",
    "/categorias",
    "/category",
    "/departamento",
    "/colecao",
    "/colecoes",
    "/collections",
    "/catalog",
    "/loja/",
    "/shop/",
    "/marcas/",
)

PAGINATION_KEYS = {"page", "pagina", "p", "pg"}


def _normalizar_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url


def _canonicalizar_url(url: str) -> str:
    url = _normalizar_url(url)
    if not url:
        return ""

    parsed = urlparse(url)
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    path = re.sub(r"/+", "/", path)
    if path != "/":
        path = path.rstrip("/")

    query_items = []
    for chave, valor in parse_qsl(parsed.query, keep_blank_values=True):
        chave_limpa = (chave or "").strip().lower()
        valor_limpo = (valor or "").strip()
        if not chave_limpa:
            continue
        if chave_limpa.startswith("utm_") or chave_limpa in {
            "fbclid",
            "gclid",
            "gad_source",
            "source",
            "ref",
            "amp",
            "sort",
            "order",
            "dir",
            "sessionid",
            "sid",
        }:
            continue
        query_items.append((chave_limpa, valor_limpo))

    query = urlencode(sorted(query_items), doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def _mesmo_dominio(url: str, dominio_base: str) -> bool:
    try:
        host = (urlparse(url).netloc or "").lower()
    except Exception:
        return False
    return host == dominio_base or host.endswith("." + dominio_base)


def _url_ignorada(url: str) -> bool:
    baixa = url.lower()
    return (
        any(ext in baixa for ext in IGNORED_EXTENSIONS)
        or "mailto:" in baixa
        or "tel:" in baixa
        or "whatsapp" in baixa
        or "/cart" in baixa
        or "/checkout" in baixa
        or "/login" in baixa
        or "/account" in baixa
    )


def _score_link(url: str) -> int:
    baixa = url.lower()
    score = 0
    if any(token in baixa for token in PRODUCT_HINTS):
        score += 8
    if any(token in baixa for token in CATEGORY_HINTS):
        score += 5
    if re.search(r"/[a-z0-9\-_]+/p$", baixa):
        score += 6
    if any(chave in baixa for chave in ("sitemap", "produto", "product", "categoria", "category")):
        score += 3
    score += baixa.count("/")
    return score


def _extrair_links(html: str, base_url: str, dominio_base: str) -> List[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    links: List[str] = []

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#"):
            continue

        absoluto = _canonicalizar_url(urljoin(base_url, href))
        if not absoluto:
            continue
        if not _mesmo_dominio(absoluto, dominio_base):
            continue
        if _url_ignorada(absoluto):
            continue

        links.append(absoluto)

    return sorted(set(links), key=lambda x: (-_score_link(x), x))


def _descobrir_sitemaps(url_base: str, html_home: str) -> List[str]:
    candidatos = [
        urljoin(url_base, "/sitemap.xml"),
        urljoin(url_base, "/sitemap_index.xml"),
        urljoin(url_base, "/sitemap-index.xml"),
        urljoin(url_base, "/product-sitemap.xml"),
        urljoin(url_base, "/categoria-sitemap.xml"),
    ]

    soup = BeautifulSoup(html_home or "", "html.parser")
    for link in soup.find_all("link", attrs={"rel": re.compile("sitemap", re.I)}):
        href = link.get("href")
        if href:
            candidatos.append(urljoin(url_base, href))

    vistos: List[str] = []
    for item in candidatos:
        canon = _canonicalizar_url(item)
        if canon and canon not in vistos:
            vistos.append(canon)
    return vistos


def _parse_sitemap(xml_texto: str) -> Dict[str, List[str]]:
    if not xml_texto:
        return {"urls": [], "sitemaps": []}

    try:
        root = ET.fromstring(xml_texto)
    except Exception:
        return {"urls": [], "sitemaps": []}

    urls: List[str] = []
    sitemaps: List[str] = []

    for elem in root.iter():
        tag = elem.tag.split("}", 1)[-1].lower()
        if tag != "loc" or not elem.text:
            continue

        valor = elem.text.strip()
        if not valor:
            continue

        valor_baixo = valor.lower()
        if valor_baixo.endswith(".xml") or "sitemap" in valor_baixo:
            sitemaps.append(valor)
        else:
            urls.append(valor)

    return {"urls": urls, "sitemaps": sitemaps}


def _carregar_urls_do_sitemap(url_base: str, html_home: str, dominio_base: str, limite_total: int = 10000) -> List[str]:
    fila = deque(_descobrir_sitemaps(url_base, html_home))
    vistos_sitemaps: Set[str] = set()
    urls: List[str] = []

    while fila and len(urls) < limite_total:
        sitemap_url = _canonicalizar_url(fila.popleft())
        if not sitemap_url or sitemap_url in vistos_sitemaps:
            continue
        vistos_sitemaps.add(sitemap_url)

        resp = baixar_html(sitemap_url, timeout=30)
        if not resp.get("ok"):
            continue

        parsed = _parse_sitemap(resp.get("html", ""))

        for child in parsed["sitemaps"]:
            canon_child = _canonicalizar_url(child)
            if canon_child and canon_child not in vistos_sitemaps:
                fila.append(canon_child)

        for item in parsed["urls"]:
            canon = _canonicalizar_url(item)
            if not canon:
                continue
            if not _mesmo_dominio(canon, dominio_base):
                continue
            if _url_ignorada(canon):
                continue
            urls.append(canon)
            if len(urls) >= limite_total:
                break

    return list(dict.fromkeys(urls))


def _priorizar_links(links: List[str]) -> List[str]:
    return sorted(set(links), key=lambda x: (-_score_link(x), x))


def _tem_paginacao(url: str) -> bool:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if any(chave.lower() in PAGINATION_KEYS for chave in query):
        return True
    return bool(re.search(r"/(page|pagina|pg)/\d+/?$", parsed.path, flags=re.I))


def extrair_produtos_de_site(
    url_inicial: str,
    limite_paginas: int = 800,
    limite_produtos: int = 5000,
) -> pd.DataFrame:
    url_inicial = _canonicalizar_url(url_inicial)
    if not url_inicial:
        raise ValueError("Informe uma URL válida do site da loja.")

    home = baixar_html(url_inicial, timeout=30)
    if not home.get("ok"):
        raise ValueError(
            f"Não foi possível acessar o site informado: {home.get('erro', 'falha desconhecida')}"
        )

    url_base = home.get("url", url_inicial)
    dominio_base = (urlparse(url_base).netloc or "").lower()
    html_home = home.get("html", "")

    fila = deque()
    visitados: Set[str] = set()
    produtos_visitados: Set[str] = set()

    candidatos_sitemap = _carregar_urls_do_sitemap(url_base, html_home, dominio_base)
    candidatos_home = _extrair_links(html_home, url_base, dominio_base)
    sementes = _priorizar_links([url_base] + candidatos_sitemap + candidatos_home)

    for item in sementes:
        canon = _canonicalizar_url(item)
        if canon and canon not in visitados:
            fila.append(canon)

    linhas: List[Dict] = []
    paginas_processadas = 0

    while fila and paginas_processadas < limite_paginas and len(linhas) < limite_produtos:
        atual = fila.popleft()
        if atual in visitados:
            continue

        visitados.add(atual)
        resp = home if atual == _canonicalizar_url(url_base) else baixar_html(atual, timeout=25)
        paginas_processadas += 1

        if not resp.get("ok"):
            continue

        url_final = _canonicalizar_url(resp.get("url", atual))
        html = resp.get("html", "")
        if not html:
            continue

        classificacao = classificar_pagina(html, url_final)
        if classificacao.get("is_product") and url_final not in produtos_visitados:
            extraido = extrair_produto_html(html, url_final)
            extraido = enriquecer_produto_com_ia(
                dados=extraido,
                html=html,
                url=url_final,
            )
            if extraido.get("nome") or extraido.get("descricao"):
                produtos_visitados.add(url_final)
                extraido["erro_scraper"] = ""
                linhas.append(extraido)
                if len(linhas) >= limite_produtos:
                    break

        links = _extrair_links(html, url_final, dominio_base)
        for link in links:
            if link in visitados:
                continue

            baixa = link.lower()
            if any(token in baixa for token in PRODUCT_HINTS + CATEGORY_HINTS):
                fila.appendleft(link)
            elif _tem_paginacao(link):
                fila.appendleft(link)
            else:
                fila.append(link)

    if not linhas:
        raise ValueError("Nenhum produto foi encontrado automaticamente no site informado.")

    df = pd.DataFrame(linhas)
    if "origem_arquivo_ou_url" in df.columns:
        df = df.drop_duplicates(subset=["origem_arquivo_ou_url"]).reset_index(drop=True)

    return df
