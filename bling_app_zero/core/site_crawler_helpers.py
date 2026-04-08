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


def _dominio(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


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
# META / TEXTO
# ==========================================================
def meta_content_crawler(soup: BeautifulSoup, attr: str, value: str) -> str:
    tag = soup.find("meta", attrs={attr: value})
    return tag.get("content") if tag else ""


def primeiro_texto_crawler(soup: BeautifulSoup, seletores: list[str]) -> str:
    for sel in seletores:
        el = soup.select_one(sel)
        if el:
            txt = texto_limpo_crawler(el.get_text(" ", strip=True))
            if txt:
                return txt
    return ""


def todas_imagens_crawler(soup: BeautifulSoup, base_url: str) -> str:
    imagens = []

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src")
        if src:
            imagens.append(urljoin(base_url, src))

    return " | ".join(list(dict.fromkeys(imagens))[:5])


# ==========================================================
# ESTOQUE
# ==========================================================
def detectar_estoque_crawler(html: str, soup: BeautifulSoup, padrao: int) -> int:
    html = (html or "").lower()

    if "esgotado" in html:
        return 0

    return padrao


# ==========================================================
# DETECÇÃO PRODUTO (COM ID STOQUI)
# ==========================================================
def link_parece_produto_crawler(url: str, texto_link: str = "") -> bool:

    u = (url or "").lower()

    # 🔥 STOQUI (CRÍTICO)
    if "/produto/" in u:
        return True

    if any(x in u for x in ["javascript:", "mailto:", "#"]):
        return False

    if any(x in u for x in ["/cart", "/checkout", "/login"]):
        return False

    if any(x in u for x in ["/product", "/item", "/sku", "/p/"]):
        return True

    partes = [p for p in urlparse(u).path.split("/") if p]

    if len(partes) >= 2 and len(partes[-1]) > 8:
        return True

    return False


# ==========================================================
# LINKS PRODUTOS (COM STOQUI + PRIMEIRA PÁGINA)
# ==========================================================
def extrair_links_produtos_crawler(html: str, base_url: str) -> list[str]:

    soup = BeautifulSoup(html, "html.parser")
    links = []

    dominio = _dominio(base_url)

    # ======================================================
    # 🔥 STOQUI (PEGAR PRIMEIRA PÁGINA)
    # ======================================================
    if "stoqui" in dominio:
        for a in soup.select("a[href*='/produto/']"):
            url = normalizar_url_crawler(base_url, a.get("href"))
            if url:
                links.append(url)

    # ======================================================
    # FALLBACK PADRÃO
    # ======================================================
    if not links:
        for a in soup.find_all("a", href=True):
            url = normalizar_url_crawler(base_url, a.get("href"))

            if not url:
                continue

            if not url_mesmo_dominio_crawler(base_url, url):
                continue

            texto = texto_limpo_crawler(a.get_text(" ", strip=True))

            if link_parece_produto_crawler(url, texto):
                links.append(url)

    return list(dict.fromkeys(links))


# ==========================================================
# PAGINAÇÃO (STOQUI + INFINITO)
# ==========================================================
def extrair_links_paginacao_crawler(html: str, base_url: str) -> list[str]:

    soup = BeautifulSoup(html, "html.parser")
    links = []

    dominio = _dominio(base_url)

    # ======================================================
    # STOQUI (categoria)
    # ======================================================
    if "stoqui" in dominio:
        for a in soup.select("a[href*='categoria']"):
            url = normalizar_url_crawler(base_url, a.get("href"))
            if url:
                links.append(url)

    # ======================================================
    # PADRÃO
    # ======================================================
    for a in soup.find_all("a", href=True):
        url = normalizar_url_crawler(base_url, a.get("href"))

        if not url:
            continue

        if not url_mesmo_dominio_crawler(base_url, url):
            continue

        if any(x in url.lower() for x in ["page=", "/page/", "pagina", "p="]):
            links.append(url)

    return list(dict.fromkeys(links))
