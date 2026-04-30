from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


@dataclass
class DomainCrawlResult:
    urls: list[str] = field(default_factory=list)
    sitemap_urls: int = 0
    internal_urls: int = 0
    product_like_urls: int = 0
    motivo: str = ""


PRODUCT_HINTS = [
    "/produto",
    "/product",
    "/produtos",
    "/products",
    "/p/",
    "/item",
    "/catalogo",
    "/loja/produto",
]

IGNORE_HINTS = [
    "#",
    "javascript:",
    "mailto:",
    "tel:",
    "/carrinho",
    "/cart",
    "/checkout",
    "/login",
    "/minha-conta",
    "/account",
    "/politica",
    "/privacy",
    "/termos",
    "/terms",
    "/blog",
]


def _txt(valor) -> str:
    return str(valor or "").strip()


def normalizar_url(url: str) -> str:
    url = _txt(url)
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc:
        return ""
    return url.split("#", 1)[0]


def mesmo_dominio(base_url: str, outra_url: str) -> bool:
    try:
        base = urlparse(base_url).netloc.replace("www.", "")
        outra = urlparse(outra_url).netloc.replace("www.", "")
        return bool(base and outra and base == outra)
    except Exception:
        return False


def parece_url_produto(url: str) -> bool:
    url_l = _txt(url).lower()
    if not url_l:
        return False
    if any(bad in url_l for bad in IGNORE_HINTS):
        return False
    return any(hint in url_l for hint in PRODUCT_HINTS)


def parece_html_produto(html: str) -> bool:
    texto = re.sub(r"\s+", " ", _txt(html).lower())
    if not texto:
        return False

    sinais = [
        "application/ld+json",
        "schema.org/product",
        "og:type\" content=\"product",
        "product:price:amount",
        "adicionar ao carrinho",
        "comprar",
        "calcular frete",
        "sku",
        "código do produto",
        "codigo do produto",
        "r$",
    ]
    score = sum(1 for sinal in sinais if sinal in texto)
    return score >= 2


def _sitemap_candidates(base_url: str) -> list[str]:
    base_url = normalizar_url(base_url)
    parsed = urlparse(base_url)
    raiz = f"{parsed.scheme}://{parsed.netloc}"
    return [
        f"{raiz}/sitemap.xml",
        f"{raiz}/sitemap_index.xml",
        f"{raiz}/sitemap-produtos.xml",
        f"{raiz}/sitemap_products.xml",
    ]


def _parse_sitemap(xml_text: str) -> list[str]:
    urls: list[str] = []
    xml_text = _txt(xml_text)
    if not xml_text:
        return urls

    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
    except Exception:
        return urls

    for elem in root.iter():
        tag = str(elem.tag).lower()
        if tag.endswith("loc") and elem.text:
            urls.append(_txt(elem.text))

    return urls


def coletar_urls_sitemap(base_url: str, fetcher: Callable[[str], str], limite: int = 250) -> list[str]:
    encontradas: list[str] = []
    vistos = set()

    fila = _sitemap_candidates(base_url)

    while fila and len(encontradas) < limite:
        sitemap_url = fila.pop(0)
        if sitemap_url in vistos:
            continue
        vistos.add(sitemap_url)

        xml = fetcher(sitemap_url)
        if not xml:
            continue

        locs = _parse_sitemap(xml)
        for loc in locs:
            if not mesmo_dominio(base_url, loc):
                continue
            if loc.lower().endswith(".xml") and loc not in vistos:
                fila.append(loc)
                continue
            if parece_url_produto(loc) and loc not in encontradas:
                encontradas.append(loc)
                if len(encontradas) >= limite:
                    break

    return encontradas


def coletar_links_internos(base_url: str, html: str, limite: int = 250) -> list[str]:
    base_url = normalizar_url(base_url)
    soup = BeautifulSoup(html or "", "html.parser")
    urls: list[str] = []
    vistos = set()

    for a in soup.find_all("a", href=True):
        href = _txt(a.get("href"))
        if not href:
            continue
        if any(href.lower().startswith(bad) for bad in ["#", "javascript:", "mailto:", "tel:"]):
            continue

        url = normalizar_url(urljoin(base_url, href))
        if not url or url in vistos:
            continue
        if not mesmo_dominio(base_url, url):
            continue
        if any(bad in url.lower() for bad in IGNORE_HINTS):
            continue

        vistos.add(url)
        urls.append(url)
        if len(urls) >= limite:
            break

    return urls


def descobrir_urls_produto(
    base_url: str,
    fetcher: Callable[[str], str],
    max_urls: int = 120,
    max_paginas_base: int = 30,
) -> DomainCrawlResult:
    base_url = normalizar_url(base_url)
    if not base_url:
        return DomainCrawlResult(motivo="url_vazia")

    finais: list[str] = []
    vistos = set()

    sitemap_urls = coletar_urls_sitemap(base_url, fetcher, limite=max_urls)
    for url in sitemap_urls:
        if url not in vistos:
            vistos.add(url)
            finais.append(url)
            if len(finais) >= max_urls:
                return DomainCrawlResult(finais, len(sitemap_urls), 0, len(finais), "limite_por_sitemap")

    html_base = fetcher(base_url)
    links_base = coletar_links_internos(base_url, html_base, limite=max_paginas_base) if html_base else []

    fila = list(links_base)
    paginas_visitadas = 0

    while fila and len(finais) < max_urls and paginas_visitadas < max_paginas_base:
        url = fila.pop(0)
        if url in vistos:
            continue
        vistos.add(url)
        paginas_visitadas += 1

        if parece_url_produto(url):
            finais.append(url)
            continue

        html = fetcher(url)
        if not html:
            continue

        if parece_html_produto(html):
            finais.append(url)
            continue

        for link in coletar_links_internos(base_url, html, limite=40):
            if link not in vistos and link not in fila:
                fila.append(link)

    motivo = "ok" if finais else "nenhuma_url_produto_detectada"
    return DomainCrawlResult(
        urls=finais[:max_urls],
        sitemap_urls=len(sitemap_urls),
        internal_urls=len(links_base),
        product_like_urls=len(finais),
        motivo=motivo,
    )
