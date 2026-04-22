"""
SITEMAP DISCOVERY ENGINE (PADRÃO GLOBAL)

Responsável por:
- Descobrir sitemap automaticamente
- Ler sitemap.xml e sitemap index
- Expandir sub-sitemaps
- Extrair URLs de produtos/categorias
- Filtrar lixo
- Servir como base para TODOS os fornecedores
"""

from __future__ import annotations

import gzip
import io
import re
import xml.etree.ElementTree as ET
from typing import List, Set
from urllib.parse import urljoin, urlparse

import requests


# -------------------------------
# CONFIG
# -------------------------------
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "pt-BR,pt;q=0.9",
    "Accept": "application/xml,text/xml,application/xhtml+xml,text/html;q=0.9,*/*;q=0.8",
}

TIMEOUT = 20
MAX_SITEMAPS = 50


# -------------------------------
# FUNÇÃO PRINCIPAL
# -------------------------------
def descobrir_urls_via_sitemap(url_base: str, limite: int = 2000) -> List[str]:
    """
    Descobre URLs a partir do sitemap do site.
    """
    url_base = _normalizar_url(url_base)
    if not url_base:
        return []

    dominio = _extrair_dominio(url_base)
    sitemaps_iniciais = _possiveis_sitemaps(dominio)

    urls: List[str] = []
    visitados: Set[str] = set()
    fila = list(sitemaps_iniciais)

    while fila and len(visitados) < MAX_SITEMAPS and len(urls) < limite:
        sitemap_url = fila.pop(0)
        sitemap_url = sitemap_url.strip()

        if not sitemap_url or sitemap_url in visitados:
            continue

        visitados.add(sitemap_url)

        xml_content = _baixar_xml(sitemap_url)
        if not xml_content:
            continue

        tipo = _detectar_tipo_sitemap(xml_content)

        if tipo == "index":
            sub_sitemaps = _parse_sitemap_index(xml_content)
            for sub in sub_sitemaps:
                if sub not in visitados and sub not in fila:
                    fila.append(sub)
            continue

        urls_extraidas = _parse_sitemap_urlset(xml_content)
        if urls_extraidas:
            urls.extend(urls_extraidas)

    urls = list(dict.fromkeys(urls))
    urls = _filtrar_urls_relevantes(urls, dominio=dominio)

    return urls[:limite]


# -------------------------------
# GERAR POSSÍVEIS SITEMAPS
# -------------------------------
def _possiveis_sitemaps(dominio: str) -> List[str]:
    return [
        urljoin(dominio, "/sitemap.xml"),
        urljoin(dominio, "/sitemap_index.xml"),
        urljoin(dominio, "/sitemap-index.xml"),
        urljoin(dominio, "/sitemap_products.xml"),
        urljoin(dominio, "/sitemap-products.xml"),
        urljoin(dominio, "/sitemap_produtos.xml"),
        urljoin(dominio, "/produto-sitemap.xml"),
        urljoin(dominio, "/product-sitemap.xml"),
        urljoin(dominio, "/post-sitemap.xml"),
        urljoin(dominio, "/page-sitemap.xml"),
        urljoin(dominio, "/category-sitemap.xml"),
        urljoin(dominio, "/sitemap1.xml"),
        urljoin(dominio, "/robots.txt"),
    ]


# -------------------------------
# BAIXAR XML / ROBOTS
# -------------------------------
def _baixar_xml(url: str) -> str:
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if response.status_code != 200:
            return ""

        content_type = str(response.headers.get("Content-Type", "")).lower()

        if url.lower().endswith(".gz") or "gzip" in content_type:
            try:
                return gzip.decompress(response.content).decode("utf-8", errors="ignore")
            except Exception:
                try:
                    with gzip.GzipFile(fileobj=io.BytesIO(response.content)) as gz:
                        return gz.read().decode("utf-8", errors="ignore")
                except Exception:
                    return ""

        texto = response.text or ""

        # robots.txt pode apontar sitemaps
        if "robots.txt" in url.lower():
            sitemaps = _extrair_sitemaps_do_robots(texto)
            if sitemaps:
                fake_index = "<sitemapindex>" + "".join(f"<sitemap><loc>{s}</loc></sitemap>" for s in sitemaps) + "</sitemapindex>"
                return fake_index

        return texto

    except Exception:
        return ""


# -------------------------------
# DETECTAR TIPO DE SITEMAP
# -------------------------------
def _detectar_tipo_sitemap(xml_content: str) -> str:
    conteudo = (xml_content or "").lower()

    if "<sitemapindex" in conteudo:
        return "index"

    if "<urlset" in conteudo:
        return "urlset"

    # fallback por estrutura
    try:
        root = ET.fromstring(xml_content)
        tag = root.tag.lower()
        if tag.endswith("sitemapindex"):
            return "index"
        if tag.endswith("urlset"):
            return "urlset"
    except Exception:
        pass

    return "desconhecido"


# -------------------------------
# PARSE SITEMAP INDEX
# -------------------------------
def _parse_sitemap_index(xml_content: str) -> List[str]:
    sitemaps: List[str] = []

    try:
        root = ET.fromstring(xml_content)

        for elem in root.iter():
            if elem.tag.endswith("loc") and elem.text:
                valor = elem.text.strip()
                if valor:
                    sitemaps.append(valor)

    except Exception:
        return []

    return list(dict.fromkeys(sitemaps))


# -------------------------------
# PARSE URLSET
# -------------------------------
def _parse_sitemap_urlset(xml_content: str) -> List[str]:
    urls: List[str] = []

    try:
        root = ET.fromstring(xml_content)

        for elem in root.iter():
            if elem.tag.endswith("loc") and elem.text:
                valor = elem.text.strip()
                if valor:
                    urls.append(valor)

    except Exception:
        return []

    return list(dict.fromkeys(urls))


# -------------------------------
# EXTRAI SITEMAPS DO ROBOTS.TXT
# -------------------------------
def _extrair_sitemaps_do_robots(texto: str) -> List[str]:
    encontrados: List[str] = []

    for linha in (texto or "").splitlines():
        linha_limpa = linha.strip()
        if not linha_limpa:
            continue

        if linha_limpa.lower().startswith("sitemap:"):
            valor = linha_limpa.split(":", 1)[1].strip()
            if valor:
                encontrados.append(valor)

    return list(dict.fromkeys(encontrados))


# -------------------------------
# FILTRO INTELIGENTE
# -------------------------------
def _filtrar_urls_relevantes(urls: List[str], dominio: str = "") -> List[str]:
    filtradas: List[str] = []
    dominio_host = (urlparse(dominio).netloc or "").lower().replace("www.", "")

    for u in urls:
        u = (u or "").strip()
        if not u:
            continue

        u_lower = u.lower()
        parsed = urlparse(u)
        host = (parsed.netloc or "").lower().replace("www.", "")

        # mantém apenas mesmo domínio quando informado
        if dominio_host and host and dominio_host != host:
            continue

        # ignora lixo
        if any(
            token in u_lower
            for token in [
                "blog",
                "login",
                "account",
                "cart",
                "checkout",
                "wp-admin",
                "wp-login",
                "/tag/",
                "/author/",
                "/feed",
                "utm_",
                "add-to-cart",
                "javascript:",
                "#",
            ]
        ):
            continue

        # ignora arquivos que não são páginas de produto/categoria
        if re.search(r"\.(jpg|jpeg|png|gif|webp|svg|pdf|zip|rar|mp4|mp3)$", u_lower):
            continue

        filtradas.append(u)

    return list(dict.fromkeys(filtradas))


# -------------------------------
# NORMALIZAR URL
# -------------------------------
def _normalizar_url(url: str) -> str:
    url = str(url or "").strip()
    if not url:
        return ""

    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    return url


# -------------------------------
# EXTRAIR DOMÍNIO BASE
# -------------------------------
def _extrair_dominio(url: str) -> str:
    parsed = urlparse(_normalizar_url(url))
    if not parsed.scheme or not parsed.netloc:
        return ""

    return f"{parsed.scheme}://{parsed.netloc}"
