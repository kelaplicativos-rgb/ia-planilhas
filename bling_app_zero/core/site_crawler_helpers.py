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
    href = str(href).strip()
    if not href:
        return ""
    return urljoin(base_url, href)


def url_mesmo_dominio_crawler(url_base: str, url: str) -> bool:
    try:
        d1 = urlparse(url_base).netloc.replace("www.", "").lower()
        d2 = urlparse(url).netloc.replace("www.", "").lower()
        return d1 == d2 or d2.endswith("." + d1) or d1.endswith("." + d2)
    except Exception:
        return False


def texto_limpo_crawler(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def numero_texto_crawler(valor: Any) -> str:
    texto = texto_limpo_crawler(valor)
    if not texto:
        return ""
    texto = texto.replace("R$", "").replace("r$", "").strip()
    match = re.search(r"(\d[\d\.\,]*)", texto)
    return match.group(1).strip() if match else texto


# ==========================================================
# 🔥 DETECÇÃO DE PRODUTO (MUITO MAIS FORTE)
# ==========================================================
def link_parece_produto_crawler(url: str, texto_link: str = "") -> bool:

    u = (url or "").lower()
    t = (texto_link or "").lower()

    # 🚫 lixo
    if any(x in u for x in [
        "javascript:",
        "mailto:",
        "#",
        ".jpg", ".jpeg", ".png", ".webp", ".svg", ".pdf"
    ]):
        return False

    if any(x in u for x in [
        "/cart", "/checkout", "/login", "/account", "/carrinho"
    ]):
        return False

    # ✅ padrões fortes
    if any(x in u for x in [
        "/produto",
        "/product",
        "/item",
        "/sku",
        "/p/",
    ]):
        return True

    # 🔥 NOVO: padrão slug de produto
    partes = [p for p in urlparse(u).path.split("/") if p]

    if len(partes) >= 2:
        if not any(x in u for x in [
            "categoria",
            "category",
            "search",
            "busca",
            "collections",
        ]):
            # evita páginas muito curtas tipo /contato
            if len(partes[-1]) > 8:
                return True

    # 🔥 NOVO: texto do link
    if any(p in t for p in [
        "comprar",
        "ver produto",
        "detalhes",
        "adicionar",
    ]):
        return True

    return False


# ==========================================================
# 🔥 EXTRAÇÃO LINKS PRODUTOS (MUITO MAIS FORTE)
# ==========================================================
def extrair_links_produtos_crawler(html: str, base_url: str) -> list[str]:

    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []

    for a in soup.find_all("a", href=True):

        href = a.get("href")
        url = normalizar_url_crawler(base_url, href)

        if not url:
            continue

        if not url_mesmo_dominio_crawler(base_url, url):
            continue

        texto = texto_limpo_crawler(a.get_text(" ", strip=True))

        if link_parece_produto_crawler(url, texto):
            links.append(url)

    # 🔥 NOVO: fallback agressivo (ESSENCIAL)
    if len(links) < 5:
        for a in soup.select("a[href]"):
            href = a.get("href")
            url = normalizar_url_crawler(base_url, href)

            if not url:
                continue

            if url_mesmo_dominio_crawler(base_url, url):
                if len(url) > 20 and "/" in url:
                    links.append(url)

    # remover duplicados
    vistos = set()
    unicos = []

    for link in links:
        if link not in vistos:
            vistos.add(link)
            unicos.append(link)

    return unicos


# ==========================================================
# PAGINAÇÃO
# ==========================================================
def extrair_links_paginacao_crawler(html: str, base_url: str) -> list[str]:

    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []

    for a in soup.find_all("a", href=True):
        href = a.get("href")
        url = normalizar_url_crawler(base_url, href)

        if not url:
            continue

        if not url_mesmo_dominio_crawler(base_url, url):
            continue

        if any(x in url.lower() for x in [
            "page=", "/page/", "pagina", "p="
        ]):
            links.append(url)

    # remover duplicados
    vistos = set()
    unicos = []

    for link in links:
        if link not in vistos:
            vistos.add(link)
            unicos.append(link)

    return unicos
