from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


# ==========================================================
# CONFIG
# ==========================================================
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

MAX_THREADS = 10
TIMEOUT = 15


# ==========================================================
# FETCH ROBUSTO
# ==========================================================
def _fetch(url: str) -> str | None:
    url = str(url or "").strip()
    if not url:
        return None

    for _ in range(3):
        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=TIMEOUT,
                allow_redirects=True,
            )
            if response.status_code == 200:
                response.encoding = response.encoding or response.apparent_encoding or "utf-8"
                return response.text
        except Exception:
            time.sleep(1)

    return None


# ==========================================================
# HELPERS
# ==========================================================
def _texto_limpo(valor: str) -> str:
    return str(valor or "").replace("\xa0", " ").strip()


def _texto(soup: BeautifulSoup, selectors: list[str]) -> str:
    for selector in selectors:
        try:
            el = soup.select_one(selector)
            if el:
                texto = el.get_text(" ", strip=True)
                if texto:
                    return _texto_limpo(texto)
        except Exception:
            continue
    return ""


def _atributo(soup: BeautifulSoup, selectors: list[str], attr: str) -> str:
    for selector in selectors:
        try:
            el = soup.select_one(selector)
            if el:
                valor = el.get(attr)
                if valor:
                    return _texto_limpo(valor)
        except Exception:
            continue
    return ""


def _normalizar_preco(valor: str) -> str:
    texto = _texto_limpo(valor)
    if not texto:
        return ""

    texto = texto.replace("R$", "").replace("r$", "").strip()
    return texto


def _detectar_estoque(html: str, soup: BeautifulSoup) -> int:
    texto_html = str(html or "").lower()
    texto_pagina = soup.get_text(" ", strip=True).lower()

    termos_sem_estoque = [
        "esgotado",
        "indisponível",
        "indisponivel",
        "sem estoque",
        "out of stock",
    ]
    if any(t in texto_html or t in texto_pagina for t in termos_sem_estoque):
        return 0

    termos_com_estoque = [
        "comprar",
        "adicionar ao carrinho",
        "adicionar à sacola",
        "disponível",
        "disponivel",
        "em estoque",
    ]
    if any(t in texto_html or t in texto_pagina for t in termos_com_estoque):
        return 10

    return 0


def _mesmo_dominio(base_url: str, link: str) -> bool:
    try:
        base_host = urlparse(base_url).netloc.lower().replace("www.", "")
        link_host = urlparse(link).netloc.lower().replace("www.", "")
        return bool(base_host and link_host and base_host == link_host)
    except Exception:
        return False


# ==========================================================
# IA DE EXTRAÇÃO
# ==========================================================
def _extrair_produto(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    nome = _texto(
        soup,
        [
            "h1",
            ".product-title",
            ".product-name",
            ".produto_nome",
            ".product_title",
            "[class*='product-title']",
            "[class*='product-name']",
        ],
    )

    preco = _texto(
        soup,
        [
            ".price",
            ".valor",
            ".product-price",
            ".price-current",
            ".woocommerce-Price-amount",
            "[class*='price']",
            "[class*='valor']",
        ],
    )

    descricao = _texto(
        soup,
        [
            ".description",
            ".product-description",
            ".woocommerce-product-details__short-description",
            "[class*='description']",
            "[class*='descricao']",
        ],
    )

    imagem = _atributo(
        soup,
        [
            "meta[property='og:image']",
            ".product-gallery img",
            ".woocommerce-product-gallery img",
            ".product img",
            "img",
        ],
        "content",
    )

    if not imagem:
        imagem = _atributo(
            soup,
            [
                ".product-gallery img",
                ".woocommerce-product-gallery img",
                ".product img",
                "img",
            ],
            "src",
        )

    imagem = urljoin(url, imagem) if imagem else ""
    estoque = _detectar_estoque(html, soup)

    return {
        "Nome": nome,
        "Preço": _normalizar_preco(preco),
        "Descrição": descricao,
        "Imagem": imagem,
        "Link": url,
        "Estoque": estoque,
    }


# ==========================================================
# COLETAR LINKS
# ==========================================================
def _extrair_links(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    vistos = set()

    for a in soup.select("a[href]"):
        href = _texto_limpo(a.get("href"))
        if not href:
            continue

        link_absoluto = urljoin(base_url, href)
        link_lower = link_absoluto.lower()

        if not link_lower.startswith(("http://", "https://")):
            continue

        if not _mesmo_dominio(base_url, link_absoluto):
            continue

        if any(bloqueado in link_lower for bloqueado in ["#", "javascript:", "mailto:", "whatsapp:"]):
            continue

        if "produto" in link_lower or "product" in link_lower:
            if link_absoluto not in vistos:
                vistos.add(link_absoluto)
                links.append(link_absoluto)

    return links


# ==========================================================
# CRAWLER PRINCIPAL
# ==========================================================
def executar_crawler(url: str) -> pd.DataFrame:
    url = str(url or "").strip()
    if not url:
        return pd.DataFrame()

    html = _fetch(url)
    if not html:
        return pd.DataFrame()

    links = _extrair_links(html, url)

    # fallback: se a própria URL já for de produto
    if not links:
        url_lower = url.lower()
        if "produto" in url_lower or "product" in url_lower:
            links = [url]

    resultados = []
    vistos_links = set()

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {
            executor.submit(_fetch, link): link
            for link in links
            if link not in vistos_links and not vistos_links.add(link)
        }

        for future in as_completed(futures):
            link = futures[future]

            try:
                html_prod = future.result()
                if not html_prod:
                    continue

                produto = _extrair_produto(html_prod, link)

                if produto.get("Nome"):
                    resultados.append(produto)

            except Exception:
                continue

    if not resultados:
        return pd.DataFrame()

    df = pd.DataFrame(resultados)
    df = df.drop_duplicates(subset=["Link"], keep="first").reset_index(drop=True)
    return df
