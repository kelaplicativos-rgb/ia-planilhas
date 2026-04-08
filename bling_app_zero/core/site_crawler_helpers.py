from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup


# ==========================================================
# VERSION
# ==========================================================
HELPERS_VERSION = "V2_MODULAR_OK"


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

    url = urljoin(base_url, href)

    try:
        parsed = urlparse(url)
        url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
    except Exception:
        pass

    return url


def url_mesmo_dominio_crawler(url_base: str, url: str) -> bool:
    try:
        d1 = urlparse(str(url_base or "")).netloc.replace("www.", "").lower()
        d2 = urlparse(str(url or "")).netloc.replace("www.", "").lower()

        if not d1 or not d2:
            return False

        return d1 == d2 or d2.endswith("." + d1) or d1.endswith("." + d2)
    except Exception:
        return False


def texto_limpo_crawler(valor: Any) -> str:
    return re.sub(r"\s+", " ", str(valor or "")).strip()


def numero_texto_crawler(valor: Any) -> str:
    texto = texto_limpo_crawler(valor)
    texto = texto.replace("R$", "").replace("r$", "").strip()

    # tenta pegar preço completo primeiro
    m = re.search(r"(\d{1,3}(?:[\.\,]\d{3})*(?:[\.\,]\d{2}))", texto)
    if m:
        return m.group(1)

    # fallback simples
    m2 = re.search(r"(\d+)", texto)
    return m2.group(1) if m2 else ""


# ==========================================================
# JSON-LD
# ==========================================================
def extrair_json_ld_crawler(soup: BeautifulSoup) -> list[dict]:
    dados: list[dict] = []

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            conteudo = script.string or script.text
            if not conteudo:
                continue

            json_data = json.loads(conteudo)

            if isinstance(json_data, list):
                dados.extend([x for x in json_data if isinstance(x, dict)])
            elif isinstance(json_data, dict):
                dados.append(json_data)
        except Exception:
            continue

    return dados


def buscar_produto_jsonld_crawler(jsonlds: list[dict]) -> dict:
    for item in jsonlds:
        if isinstance(item, dict) and "product" in str(item.get("@type", "")).lower():
            return item
    return {}


# ==========================================================
# META / TEXTO
# ==========================================================
def meta_content_crawler(soup: BeautifulSoup, attr: str, value: str) -> str:
    tag = soup.find("meta", attrs={attr: value})
    return str(tag.get("content", "")).strip() if tag else ""


def primeiro_texto_crawler(soup: BeautifulSoup, seletores: list[str]) -> str:
    for sel in seletores:
        el = soup.select_one(sel)
        if el:
            txt = texto_limpo_crawler(el.get_text(" ", strip=True))
            if txt:
                return txt
    return ""


def todas_imagens_crawler(soup: BeautifulSoup, base_url: str) -> str:
    imagens: list[str] = []

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if not src:
            continue

        url = normalizar_url_crawler(base_url, src)
        if not url:
            continue

        if not any(x in url.lower() for x in ["logo", "icon", "placeholder", "thumb"]):
            if url not in imagens:
                imagens.append(url)

    return " | ".join(imagens[:5])


# ==========================================================
# ESTOQUE
# ==========================================================
def detectar_estoque_crawler(html: str, soup: BeautifulSoup, padrao: int) -> int:
    html_baixo = (html or "").lower()

    sinais_esgotado = [
        "esgotado",
        "indisponível",
        "indisponivel",
        "out of stock",
        "sem estoque",
    ]
    if any(x in html_baixo for x in sinais_esgotado):
        return 0

    sinais_disponivel = [
        "comprar",
        "adicionar ao carrinho",
        "adicionar",
        "buy now",
        "em estoque",
        "disponível",
        "disponivel",
    ]
    if any(x in html_baixo for x in sinais_disponivel):
        return padrao

    return padrao


# ==========================================================
# DETECÇÃO DE PRODUTO
# ==========================================================
def link_parece_produto_crawler(url: str) -> bool:
    u = (url or "").lower()

    if any(x in u for x in [
        "javascript:",
        "mailto:",
        "#",
        "login",
        "conta",
        "carrinho",
        "checkout",
        "categoria",
        "category",
    ]):
        return False

    sinais = [
        "/produto",
        "/product",
        "/p/",
        "/prod/",
        "/item/",
        "/sku/",
        "produto-",
        "product-",
    ]

    return any(s in u for s in sinais)


# ==========================================================
# LINKS PRODUTOS
# ==========================================================
def extrair_links_produtos_crawler(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []

    for a in soup.select("a[href]"):
        href = a.get("href")

        url = normalizar_url_crawler(base_url, href)
        if not url:
            continue

        if not url_mesmo_dominio_crawler(base_url, url):
            continue

        if link_parece_produto_crawler(url):
            links.append(url)

    return list(dict.fromkeys(links))


# ==========================================================
# PAGINAÇÃO
# ==========================================================
def extrair_links_paginacao_crawler(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []

    for a in soup.select("a[href]"):
        url = normalizar_url_crawler(base_url, a.get("href"))

        if not url:
            continue

        if not url_mesmo_dominio_crawler(base_url, url):
            continue

        if any(x in url.lower() for x in [
            "page=",
            "pagina",
            "/page/",
            "/pagina/",
            "?p=",
            "&p=",
            "pg=",
            "offset",
            "start",
        ]):
            links.append(url)

    return list(dict.fromkeys(links))
