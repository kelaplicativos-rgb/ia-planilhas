
from __future__ import annotations

import re
from typing import Iterable
from urllib.parse import quote_plus, urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0 Mobile Safari/537.36"
    )
}


def _normalizar_base_url(url: str) -> str:
    url = str(url or "").strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url.rstrip("/")


def _dominio(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _mesmo_dominio(url_base: str, url_alvo: str) -> bool:
    return _dominio(url_base) == _dominio(url_alvo)


def _urls_busca(base_url: str, termo: str) -> list[str]:
    termo_enc = quote_plus(termo.strip())
    base = _normalizar_base_url(base_url)

    candidatos = [
        f"{base}/search?q={termo_enc}",
        f"{base}/busca?q={termo_enc}",
        f"{base}/busca?search={termo_enc}",
        f"{base}/busca?descricao={termo_enc}",
        f"{base}/catalogsearch/result/?q={termo_enc}",
        f"{base}/?s={termo_enc}",
        f"{base}/?q={termo_enc}",
    ]

    vistos: set[str] = set()
    saida: list[str] = []
    for item in candidatos:
        if item not in vistos:
            vistos.add(item)
            saida.append(item)
    return saida


def _extrair_preco(texto: str) -> str:
    if not texto:
        return ""
    match = re.search(r"R\$\s*\d[\d\.\,]*", texto, flags=re.I)
    return match.group(0).strip() if match else ""


def _link_parece_produto(href: str, texto: str, termo: str) -> bool:
    href_n = str(href or "").lower()
    texto_n = str(texto or "").lower()
    termo_n = str(termo or "").lower()

    pistas_href = [
        "/produto",
        "/product",
        "/item",
        "/p/",
        "sku",
    ]
    if any(p in href_n for p in pistas_href):
        return True

    if termo_n and termo_n in texto_n:
        return True

    palavras = termo_n.split()
    if palavras and sum(1 for p in palavras if p in texto_n) >= max(1, len(palavras) // 2):
        return True

    return False


def _coletar_links_produto(
    html: str,
    base_url: str,
    termo: str,
    limite: int = 50,
) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    encontrados: list[dict] = []
    vistos: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = str(a.get("href") or "").strip()
        texto = " ".join(a.stripped_strings).strip()
        if not href:
            continue

        url_abs = urljoin(base_url, href)
        if not _mesmo_dominio(base_url, url_abs):
            continue
        if url_abs in vistos:
            continue
        if not _link_parece_produto(url_abs, texto, termo):
            continue

        bloco_texto = ""
        try:
            bloco_texto = a.parent.get_text(" ", strip=True)[:500]
        except Exception:
            bloco_texto = texto

        encontrados.append(
            {
                "produto": texto or "Produto encontrado",
                "url": url_abs,
                "preco": _extrair_preco(bloco_texto),
                "fonte": "busca_site",
            }
        )
        vistos.add(url_abs)

        if len(encontrados) >= limite:
            break

    return encontrados


def buscar_produtos_fornecedor(
    base_url: str,
    termo: str,
    limite: int = 30,
    timeout: int = 12,
) -> pd.DataFrame:
    base = _normalizar_base_url(base_url)
    termo = str(termo or "").strip()

    if not base:
        return pd.DataFrame(columns=["produto", "url", "preco", "fonte", "url_busca"])

    if not termo:
        return pd.DataFrame(columns=["produto", "url", "preco", "fonte", "url_busca"])

    sess = requests.Session()
    sess.headers.update(HEADERS)

    resultados: list[dict] = []

    for url_busca in _urls_busca(base, termo):
        try:
            resp = sess.get(url_busca, timeout=timeout, allow_redirects=True)
            if resp.status_code >= 400:
                continue

            itens = _coletar_links_produto(
                html=resp.text,
                base_url=base,
                termo=termo,
                limite=limite,
            )

            for item in itens:
                item["url_busca"] = url_busca
                resultados.append(item)

            if resultados:
                break

        except Exception:
            continue

    if not resultados:
        return pd.DataFrame(
            columns=["produto", "url", "preco", "fonte", "url_busca"]
        )

    df = pd.DataFrame(resultados).drop_duplicates(subset=["url"]).head(limite)
    return df.reset_index(drop=True)
