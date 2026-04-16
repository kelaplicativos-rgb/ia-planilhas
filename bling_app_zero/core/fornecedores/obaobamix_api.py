
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Iterable
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

TIMEOUT = 20
BASE_URL = "https://obaobamix.com.br/"


# ============================================================
# HELPERS
# ============================================================

def _safe_str(valor: Any) -> str:
    if valor is None:
        return ""
    texto = str(valor).strip()
    if texto.lower() in {"none", "nan", "nat"}:
        return ""
    return texto


def _normalizar_texto(valor: Any) -> str:
    texto = _safe_str(valor).lower()
    trocas = {
        "ã": "a",
        "á": "a",
        "à": "a",
        "â": "a",
        "é": "e",
        "ê": "e",
        "í": "i",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ú": "u",
        "ç": "c",
        "_": " ",
        "-": " ",
    }
    for origem, destino in trocas.items():
        texto = texto.replace(origem, destino)
    return " ".join(texto.split())


def _headers():
    return {"User-Agent": USER_AGENT}


def _soup(url: str):
    resp = requests.get(url, headers=_headers(), timeout=TIMEOUT)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def _url_mesmo_dominio(url_a: str, url_b: str) -> bool:
    try:
        return urlparse(url_a).netloc.replace("www.", "") == urlparse(url_b).netloc.replace("www.", "")
    except Exception:
        return False


def _deduplicar(valores: Iterable[str]) -> list[str]:
    vistos = set()
    out = []
    for v in valores:
        v = _safe_str(v)
        if v and v not in vistos:
            vistos.add(v)
            out.append(v)
    return out


def _formatar_preco(valor: Any) -> str:
    txt = _safe_str(valor).replace("R$", "").replace(" ", "")
    txt = txt.replace(".", "").replace(",", ".")
    try:
        return f"{float(txt):.2f}".replace(".", ",")
    except:
        return ""


# ============================================================
# LISTAS
# ============================================================

def _seeds():
    return [
        BASE_URL,
        urljoin(BASE_URL, "produtos"),
        urljoin(BASE_URL, "ofertas"),
    ]


def _links_produto(url_lista: str) -> list[str]:
    links = []
    try:
        soup = _soup(url_lista)
    except:
        return links

    for a in soup.find_all("a", href=True):
        href = urljoin(url_lista, a.get("href"))
        if not _url_mesmo_dominio(url_lista, href):
            continue
        if "/produto/" in href or re.search(r"/\d{5,}", href):
            links.append(href)

    return _deduplicar(links)


# ============================================================
# EXTRAÇÃO
# ============================================================

def _jsonld(soup):
    out = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string)
            if isinstance(data, dict):
                out.append(data)
            elif isinstance(data, list):
                out.extend(data)
        except:
            continue
    return out


def _extrair_produto(url: str) -> dict:
    try:
        soup = _soup(url)
        j = _jsonld(soup)

        nome = ""
        preco = ""
        gtin = ""

        for item in j:
            if item.get("name"):
                nome = item.get("name")
            if item.get("offers"):
                preco = item["offers"].get("price")
            if item.get("gtin"):
                gtin = item.get("gtin")

        if not nome:
            h1 = soup.find("h1")
            nome = _safe_str(h1.text if h1 else "")

        texto = soup.get_text(" ", strip=True).lower()

        if any(x in texto for x in ["sem estoque", "esgotado"]):
            qtd = 0
        else:
            qtd = 10

        imagens = []
        for img in soup.find_all("img"):
            src = _safe_str(img.get("src"))
            if src and _url_mesmo_dominio(url, src):
                imagens.append(urljoin(url, src))

        return {
            "codigo_fornecedor": url.split("/")[-1],
            "descricao_fornecedor": nome,
            "preco_base": _formatar_preco(preco),
            "quantidade_real": qtd,
            "gtin": gtin,
            "categoria": "",
            "url_imagens": "|".join(_deduplicar(imagens[:5])),
            "link_produto": url,
        }

    except:
        return {}


# ============================================================
# API PRINCIPAL
# ============================================================

def buscar_produtos_oba_oba_mix(
    fornecedor: str = "oba_oba_mix",
    categoria: str = "",
    operacao: str = "",
    config: dict | None = None,
) -> pd.DataFrame:
    _ = fornecedor, categoria, operacao, config

    links = []
    for seed in _seeds():
        links.extend(_links_produto(seed))

    links = _deduplicar(links)

    produtos = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(_extrair_produto, l) for l in links]
        for f in as_completed(futures):
            r = f.result()
            if r and r.get("descricao_fornecedor"):
                produtos.append(r)

    if not produtos:
        return pd.DataFrame()

    df = pd.DataFrame(produtos).fillna("")

    if "preco_base" in df:
        df["preco_base"] = df["preco_base"].apply(_formatar_preco)

    if "quantidade_real" in df:
        df["quantidade_real"] = pd.to_numeric(df["quantidade_real"], errors="coerce").fillna(0).astype(int)

    return df.reset_index(drop=True)
