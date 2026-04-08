from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


MAX_THREADS = 12
MAX_PAGINAS = 12
MAX_PRODUTOS = 1200


# ==========================================================
# URL / TEXTO
# ==========================================================
def normalizar_url_crawler(base_url: str, href: str | None) -> str:
    if not href:
        return ""
    return urljoin(base_url, str(href).strip())


def url_mesmo_dominio_crawler(url_base: str, url: str) -> bool:
    try:
        d1 = urlparse(url_base).netloc.replace("www.", "").lower()
        d2 = urlparse(url).netloc.replace("www.", "").lower()
        return d1 == d2 or d2.endswith("." + d1)
    except Exception:
        return False


def texto_limpo_crawler(valor: Any) -> str:
    return re.sub(r"\s+", " ", str(valor or "")).strip()


def numero_texto_crawler(valor: Any) -> str:
    texto = texto_limpo_crawler(valor)
    texto = texto.replace("R$", "").strip()
    m = re.search(r"(\d[\d\.\,]*)", texto)
    return m.group(1) if m else ""


# ==========================================================
# JSON-LD
# ==========================================================
def extrair_json_ld_crawler(soup: BeautifulSoup) -> list[dict]:
    dados = []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            conteudo = script.string or script.text
            if not conteudo:
                continue

            json_data = json.loads(conteudo)

            if isinstance(json_data, list):
                dados.extend(json_data)
            else:
                dados.append(json_data)

        except Exception:
            continue

    return dados


def buscar_produto_jsonld_crawler(jsonlds: list[dict]) -> dict:
    for item in jsonlds:
        if isinstance(item, dict):
            if "product" in str(item.get("@type", "")).lower():
                return item
    return {}


# ==========================================================
# LINKS PRODUTOS (NÍVEL PRODUÇÃO)
# ==========================================================
def extrair_links_produtos_crawler(html: str, base_url: str) -> list[str]:

    soup = BeautifulSoup(html, "html.parser")
    links = []

    # 🔥 1. tenta padrões conhecidos
    seletores = [
        "a[href*='produto']",
        "a[href*='product']",
        "a[href*='/p/']",
        "a[href*='sku']",
        "a[href*='id=']",
    ]

    for sel in seletores:
        for a in soup.select(sel):
            url = normalizar_url_crawler(base_url, a.get("href"))

            if not url:
                continue

            if not url_mesmo_dominio_crawler(base_url, url):
                continue

            links.append(url)

    # 🔥 2. fallback por estrutura (cards de produto)
    if not links:
        for card in soup.select("[class*='product'], [class*='card'], li"):
            a = card.find("a", href=True)
            if not a:
                continue

            url = normalizar_url_crawler(base_url, a.get("href"))

            if not url:
                continue

            if not url_mesmo_dominio_crawler(base_url, url):
                continue

            # evita lixo
            if any(x in url.lower() for x in ["login", "conta", "carrinho"]):
                continue

            links.append(url)

    # 🔥 3. fallback bruto (último nível)
    if not links:
        for a in soup.select("a[href]"):
            url = normalizar_url_crawler(base_url, a.get("href"))

            if not url:
                continue

            if not url_mesmo_dominio_crawler(base_url, url):
                continue

            if any(x in url.lower() for x in [
                "login",
                "conta",
                "carrinho",
                "checkout",
                "javascript",
                "#",
            ]):
                continue

            # heurística forte
            if len(urlparse(url).path) > 10:
                links.append(url)

    return list(dict.fromkeys(links))


# ==========================================================
# DETECÇÃO PRODUTO (MELHORADA)
# ==========================================================
def link_parece_produto_crawler(url: str, texto_link: str = "") -> bool:

    u = (url or "").lower()

    if any(x in u for x in ["javascript:", "mailto:", "#"]):
        return False

    if any(x in u for x in ["cart", "checkout", "login"]):
        return False

    path = urlparse(u).path

    # 🔥 produto geralmente tem path mais profundo
    if len(path.split("/")) >= 2 and len(path) > 15:
        return True

    return False


# ==========================================================
# PAGINAÇÃO
# ==========================================================
def extrair_links_paginacao_crawler(html: str, base_url: str) -> list[str]:

    soup = BeautifulSoup(html, "html.parser")
    links = []

    for a in soup.select("a[href]"):
        url = normalizar_url_crawler(base_url, a.get("href"))

        if not url:
            continue

        if not url_mesmo_dominio_crawler(base_url, url):
            continue

        if any(x in url.lower() for x in ["page=", "pagina", "?p=", "&p="]):
            links.append(url)

    return list(dict.fromkeys(links))
