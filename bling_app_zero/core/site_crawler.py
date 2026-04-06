from __future__ import annotations

import time
import requests
import pandas as pd

from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


# ==========================================================
# CONFIG
# ==========================================================
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

MAX_THREADS = 10
TIMEOUT = 15


# ==========================================================
# FETCH ROBUSTO
# ==========================================================
def _fetch(url: str) -> str | None:
    for _ in range(3):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.text
        except Exception:
            time.sleep(1)
    return None


# ==========================================================
# IA DE EXTRAÇÃO
# ==========================================================
def _extrair_produto(html: str, url: str) -> dict:

    soup = BeautifulSoup(html, "html.parser")

    def texto(selector):
        el = soup.select_one(selector)
        return el.get_text(strip=True) if el else ""

    def atributo(selector, attr):
        el = soup.select_one(selector)
        return el.get(attr) if el else ""

    # 🔥 IA heurística
    nome = (
        texto("h1")
        or texto(".product-title")
        or texto(".product-name")
    )

    preco = (
        texto(".price")
        or texto(".valor")
        or texto(".product-price")
    )

    descricao = (
        texto(".description")
        or texto(".product-description")
    )

    imagem = atributo("img", "src")

    estoque = 10
    if "esgotado" in html.lower():
        estoque = 0

    return {
        "Nome": nome,
        "Preço": preco,
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

    for a in soup.select("a"):
        href = a.get("href")

        if not href:
            continue

        if "produto" in href or "product" in href:
            if href.startswith("/"):
                href = base_url.rstrip("/") + href

            links.append(href)

    return list(set(links))


# ==========================================================
# CRAWLER PRINCIPAL
# ==========================================================
def executar_crawler(url: str) -> pd.DataFrame:

    html = _fetch(url)

    if not html:
        return pd.DataFrame()

    links = _extrair_links(html, url)

    resultados = []

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:

        futures = {
            executor.submit(_fetch, link): link
            for link in links
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

    return pd.DataFrame(resultados)
