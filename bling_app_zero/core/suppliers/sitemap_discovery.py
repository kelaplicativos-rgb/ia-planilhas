"""
SITEMAP DISCOVERY ENGINE (PADRÃO GLOBAL)

Responsável por:
- Descobrir sitemap automaticamente
- Ler sitemap.xml e sitemap index
- Extrair URLs de produtos/categorias
- Servir como base para TODOS os fornecedores
"""

import requests
import xml.etree.ElementTree as ET
from typing import List
from urllib.parse import urljoin, urlparse


# -------------------------------
# CONFIG
# -------------------------------
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "pt-BR,pt;q=0.9"
}

TIMEOUT = 15


# -------------------------------
# FUNÇÃO PRINCIPAL
# -------------------------------
def descobrir_urls_via_sitemap(url_base: str, limite: int = 2000) -> List[str]:
    """
    Descobre URLs a partir do sitemap do site
    """

    dominio = _extrair_dominio(url_base)

    possiveis_sitemaps = [
        urljoin(dominio, "/sitemap.xml"),
        urljoin(dominio, "/sitemap_index.xml"),
        urljoin(dominio, "/sitemap-products.xml"),
        urljoin(dominio, "/sitemap_produtos.xml"),
    ]

    urls = []

    for sitemap_url in possiveis_sitemaps:

        xml_content = _baixar_xml(sitemap_url)

        if not xml_content:
            continue

        urls.extend(_parse_sitemap(xml_content))

    # deduplicação
    urls = list(dict.fromkeys(urls))

    # filtro básico
    urls = _filtrar_urls_relevantes(urls)

    return urls[:limite]


# -------------------------------
# BAIXAR XML
# -------------------------------
def _baixar_xml(url: str) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)

        if r.status_code != 200:
            return ""

        return r.text

    except Exception:
        return ""


# -------------------------------
# PARSE XML
# -------------------------------
def _parse_sitemap(xml_content: str) -> List[str]:

    urls = []

    try:
        root = ET.fromstring(xml_content)

        for elem in root.iter():
            if elem.tag.endswith("loc") and elem.text:
                urls.append(elem.text.strip())

    except Exception:
        return []

    return urls


# -------------------------------
# FILTRO INTELIGENTE
# -------------------------------
def _filtrar_urls_relevantes(urls: List[str]) -> List[str]:

    filtradas = []

    for u in urls:

        u_lower = u.lower()

        # ignora lixo
        if any(x in u_lower for x in [
            "blog",
            "login",
            "account",
            "cart",
            "checkout",
            "wp-admin",
            "wp-login"
        ]):
            continue

        filtradas.append(u)

    return filtradas


# -------------------------------
# EXTRAIR DOMÍNIO BASE
# -------------------------------
def _extrair_dominio(url: str) -> str:

    parsed = urlparse(url)

    return f"{parsed.scheme}://{parsed.netloc}"
