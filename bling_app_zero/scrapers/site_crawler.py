import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import pandas as pd


HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def is_valid_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return bool(parsed.netloc) and bool(parsed.scheme)
    except:
        return False


def coletar_links_internos(url_base: str, max_links: int = 50):
    try:
        resp = requests.get(url_base, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "lxml")

        links = set()

        for a in soup.find_all("a", href=True):
            href = urljoin(url_base, a["href"])

            if url_base in href:
                links.add(href)

            if len(links) >= max_links:
                break

        return list(links)

    except Exception:
        return []


def extrair_dados_produto(url: str):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "lxml")

        nome = soup.find("h1")
        preco = soup.find(text=lambda x: x and "R$" in x)

        imagens = [
            img.get("src")
            for img in soup.find_all("img")
            if img.get("src")
        ]

        return {
            "url": url,
            "nome": nome.get_text(strip=True) if nome else "",
            "preco": preco.strip() if preco else "",
            "imagens": ",".join(imagens[:3]),
        }

    except Exception:
        return None


def extrair_produtos_de_site(url: str) -> pd.DataFrame:
    if not is_valid_url(url):
        return pd.DataFrame()

    links = coletar_links_internos(url)

    produtos = []

    for link in links:
        dados = extrair_dados_produto(link)
        if dados:
            produtos.append(dados)

    return pd.DataFrame(produtos)
