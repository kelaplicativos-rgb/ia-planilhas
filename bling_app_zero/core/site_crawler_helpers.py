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
# JSON-LD
# ==========================================================
def extrair_json_ld_crawler(soup: BeautifulSoup) -> list[dict]:
    itens: list[dict] = []

    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        bruto = tag.string or tag.get_text(" ", strip=True)
        if not bruto:
            continue

        try:
            data = json.loads(bruto)
            if isinstance(data, list):
                itens.extend([i for i in data if isinstance(i, dict)])
            elif isinstance(data, dict):
                itens.append(data)
        except Exception:
            continue

    return itens


def buscar_produto_jsonld_crawler(jsonlds: list[dict]) -> dict:
    for item in jsonlds:
        tipo = str(item.get("@type", "")).lower()
        if "product" in tipo:
            return item

        graph = item.get("@graph")
        if isinstance(graph, list):
            for sub in graph:
                if isinstance(sub, dict) and "product" in str(sub.get("@type", "")).lower():
                    return sub

    return {}


# ==========================================================
# META / SELETORES
# ==========================================================
def meta_content_crawler(soup: BeautifulSoup, attr: str, valor: str) -> str:
    tag = soup.find("meta", attrs={attr: valor})
    if tag and tag.get("content"):
        return texto_limpo_crawler(tag.get("content"))
    return ""


def primeiro_texto_crawler(soup: BeautifulSoup, seletores: list[str]) -> str:
    for seletor in seletores:
        try:
            el = soup.select_one(seletor)
            if el:
                texto = texto_limpo_crawler(el.get_text(" ", strip=True))
                if texto:
                    return texto
        except Exception:
            continue
    return ""


def primeiro_attr_crawler(soup: BeautifulSoup, seletores: list[str], attr: str) -> str:
    for seletor in seletores:
        try:
            el = soup.select_one(seletor)
            if el and el.get(attr):
                valor = texto_limpo_crawler(el.get(attr))
                if valor:
                    return valor
        except Exception:
            continue
    return ""


# ==========================================================
# IMAGENS
# ==========================================================
def todas_imagens_crawler(soup: BeautifulSoup, base_url: str) -> str:
    candidatos: list[str] = []

    for img in soup.select("img"):
        for attr in ["data-zoom-image", "data-large_image", "data-src", "src"]:
            valor = img.get(attr)
            if valor:
                candidatos.append(normalizar_url_crawler(base_url, valor))

    vistos = []
    for url in candidatos:
        if url and url not in vistos and not url.lower().endswith(".svg"):
            vistos.append(url)

    return " | ".join(vistos[:10])


# ==========================================================
# ESTOQUE
# ==========================================================
def detectar_estoque_crawler(
    html: str,
    soup: BeautifulSoup,
    padrao_disponivel: int = 10,
) -> int:

    texto = " ".join(
        [
            texto_limpo_crawler(soup.get_text(" ", strip=True)).lower(),
            str(html).lower(),
        ]
    )

    if any(p in texto for p in ["esgotado", "out of stock", "sem estoque"]):
        return 0

    if any(p in texto for p in ["comprar", "add to cart", "buy now"]):
        return padrao_disponivel

    return padrao_disponivel


# ==========================================================
# 🔥 DETECÇÃO INTELIGENTE DE PRODUTO (CORRIGIDO)
# ==========================================================
def link_parece_produto_crawler(url: str) -> bool:

    u = (url or "").lower()

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

    # ✅ sinais fortes
    sinais_fortes = [
        "/produto",
        "/product",
        "/item",
        "/sku",
        "/p/",
    ]

    if any(s in u for s in sinais_fortes):
        return True

    # 🔥 fallback inteligente (ESSENCIAL)
    partes = [p for p in urlparse(u).path.split("/") if p]

    if len(partes) >= 2:
        # evita categorias comuns
        if not any(x in u for x in [
            "categoria",
            "category",
            "search",
            "busca"
        ]):
            return True

    return False


# ==========================================================
# EXTRAÇÃO LINKS PRODUTOS (MELHORADA)
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

        # 🔥 usa texto do link como reforço
        texto = texto_limpo_crawler(a.get_text(" ", strip=True)).lower()

        if link_parece_produto_crawler(url):
            links.append(url)
            continue

        if any(p in texto for p in ["comprar", "ver produto", "detalhes"]):
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
