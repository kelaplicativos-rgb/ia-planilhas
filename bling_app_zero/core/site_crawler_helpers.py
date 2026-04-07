from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


MAX_THREADS = 12
MAX_PAGINAS = 12
MAX_PRODUTOS = 1200


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


def extrair_json_ld_crawler(soup: BeautifulSoup) -> list[dict]:
    itens: list[dict] = []

    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        bruto = tag.string or tag.get_text(" ", strip=True)
        if not bruto:
            continue

        try:
            data = json.loads(bruto)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict):
                        itens.append(item)
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


def todas_imagens_crawler(soup: BeautifulSoup, base_url: str) -> str:
    candidatos: list[str] = []

    for seletor in [
        "img",
        ".product-gallery img",
        ".gallery img",
        ".product-images img",
        ".woocommerce-product-gallery__image img",
    ]:
        try:
            for img in soup.select(seletor):
                for attr in ["data-zoom-image", "data-large_image", "data-src", "src"]:
                    valor = img.get(attr)
                    if valor:
                        candidatos.append(normalizar_url_crawler(base_url, valor))
        except Exception:
            continue

    vistos = []
    for url in candidatos:
        if url and url not in vistos and not url.lower().endswith(".svg"):
            vistos.append(url)

    return " | ".join(vistos[:10])


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

    padroes_zero = [
        "esgotado",
        "indisponível",
        "indisponivel",
        "out of stock",
        "sem estoque",
        "sold out",
    ]
    if any(p in texto for p in padroes_zero):
        return 0

    padroes_ok = [
        "comprar",
        "adicionar ao carrinho",
        "disponível",
        "disponivel",
        "em estoque",
        "buy now",
        "add to cart",
    ]
    if any(p in texto for p in padroes_ok):
        return padrao_disponivel

    return padrao_disponivel


def link_parece_produto_crawler(url: str) -> bool:
    u = (url or "").lower()
    sinais_positivos = [
        "/produto",
        "/produtos",
        "/product",
        "/p/",
        "/item/",
        "/shop/",
    ]
    sinais_ruins = [
        "/cart",
        "/checkout",
        "/account",
        "/login",
        "/conta",
        "/carrinho",
        "/wishlist",
        "/favoritos",
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".svg",
        ".pdf",
        "mailto:",
        "javascript:",
        "#",
    ]

    if any(s in u for s in sinais_ruins):
        return False

    if any(s in u for s in sinais_positivos):
        return True

    partes = [p for p in urlparse(u).path.split("/") if p]
    if len(partes) >= 2:
        return True

    return False


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
        if link_parece_produto_crawler(url):
            links.append(url)

    unicos = []
    for link in links:
        if link not in unicos:
            unicos.append(link)

    return unicos


def extrair_links_paginacao_crawler(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []

    for seletor in [
        "a.next",
        "a[rel='next']",
        ".pagination a",
        ".pager a",
        ".page-numbers a",
    ]:
        try:
            for a in soup.select(seletor):
                href = a.get("href")
                url = normalizar_url_crawler(base_url, href)
                if url and url_mesmo_dominio_crawler(base_url, url):
                    links.append(url)
        except Exception:
            continue

    candidatos = []
    for link in links:
        l = link.lower()
        if any(x in l for x in ["page=", "/page/", "pagina", "p="]):
            candidatos.append(link)

    unicos = []
    for link in candidatos:
        if link not in unicos:
            unicos.append(link)

    return unicos
