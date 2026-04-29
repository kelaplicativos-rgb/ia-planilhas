"""
CRAWLER ENGINE — BLINGPERF CRAWLER FULL FIX

Objetivo:
- Rodar forte em Streamlit Cloud SEM depender de Playwright.
- Usar HTTP híbrido robusto.
- Ler sitemap, páginas, categorias, paginações e links embutidos em JS.
- Extrair produto com JSON-LD + heurística existente do projeto.
- Manter compatibilidade com SiteAgent.run_crawler().
"""

from __future__ import annotations

import concurrent.futures
import re
import time
import xml.etree.ElementTree as ET
from collections import deque
from typing import Any
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

try:
    import streamlit as st
except Exception:  # pragma: no cover
    st = None

from bling_app_zero.core.site_crawler_cleaners import (
    normalizar_texto,
    normalizar_url,
    safe_str,
)
from bling_app_zero.core.site_crawler_http import (
    extrair_detalhes_heuristicos,
    fetch_html_retry,
    normalizar_link_crawl,
    url_valida_para_crawl,
)
from bling_app_zero.core.site_crawler_links import (
    descobrir_produtos_no_dominio,
    extrair_links_pagina,
)


HEADERS_POOL = [
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    },
    {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; SM-S911B) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Mobile Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    },
]

PRODUCT_HINTS = (
    "/produto",
    "/produtos",
    "/product",
    "/products",
    "/p/",
    "/item",
    "/sku",
    "/prd",
)

BAD_LINK_HINTS = (
    "/login",
    "/logout",
    "/account",
    "/conta",
    "/cart",
    "/carrinho",
    "/checkout",
    "/politica",
    "/privacy",
    "/termos",
    "/terms",
    "mailto:",
    "tel:",
    "whatsapp",
    "javascript:",
)

SITEMAP_PATHS = (
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/product-sitemap.xml",
    "/produto-sitemap.xml",
    "/products-sitemap.xml",
    "/sitemap_products.xml",
    "/sitemap-produtos.xml",
)


def _log(msg: str) -> None:
    texto = safe_str(msg)
    if not texto:
        return

    try:
        if st is not None:
            logs = st.session_state.setdefault("logs", [])
            logs.append(texto)
    except Exception:
        pass

    try:
        print(texto)
    except Exception:
        pass


def _raiz(url: str) -> str:
    parsed = urlparse(normalizar_url(url))
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return normalizar_url(url)


def _host(url: str) -> str:
    try:
        return urlparse(normalizar_url(url)).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _mesmo_host(base_url: str, url: str) -> bool:
    return _host(base_url) == _host(url)


def _url_ruim(url: str) -> bool:
    url_n = normalizar_texto(url)
    return any(x in url_n for x in BAD_LINK_HINTS)


def _parece_produto_url(url: str) -> bool:
    url_n = normalizar_texto(url)
    if not url_n or _url_ruim(url_n):
        return False

    if any(h in url_n for h in PRODUCT_HINTS):
        return True

    path = urlparse(normalizar_url(url)).path.strip("/")
    partes = [p for p in path.split("/") if p]

    if len(partes) >= 2:
        ultimo = partes[-1]
        if "-" in ultimo and len(ultimo) >= 10:
            return True

    return False


def _parece_categoria_url(url: str) -> bool:
    url_n = normalizar_texto(url)
    sinais = (
        "/categoria",
        "/categorias",
        "/departamento",
        "/departamentos",
        "/collection",
        "/collections",
        "/busca",
        "/search",
        "page=",
        "pagina=",
        "/page/",
    )
    return any(s in url_n for s in sinais)


def _html_tem_produto(html: str) -> bool:
    html_n = normalizar_texto(html)
    sinais = (
        '"@type":"product"',
        '"@type": "product"',
        "application/ld+json",
        "product:price",
        "itemprop='price'",
        'itemprop="price"',
        "adicionar ao carrinho",
        "comprar agora",
        "add to cart",
        "sku",
        "gtin",
        "ean",
        "r$",
    )
    return any(s in html_n for s in sinais)


def _criar_session(auth_context: dict[str, Any] | None = None) -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS_POOL[0])

    if not isinstance(auth_context, dict):
        return session

    headers = auth_context.get("headers")
    if isinstance(headers, dict):
        for k, v in headers.items():
            k_s = safe_str(k)
            v_s = safe_str(v)
            if k_s and v_s:
                session.headers[k_s] = v_s

    cookies = auth_context.get("cookies")
    if isinstance(cookies, list):
        for cookie in cookies:
            if not isinstance(cookie, dict):
                continue
            nome = safe_str(cookie.get("name"))
            valor = safe_str(cookie.get("value"))
            dominio = safe_str(cookie.get("domain"))
            path = safe_str(cookie.get("path")) or "/"
            if not nome:
                continue
            try:
                session.cookies.set(nome, valor, domain=dominio or None, path=path)
            except Exception:
                continue

    return session


def _fetch(session: requests.Session, url: str, timeout: int = 35) -> str:
    url = normalizar_url(url)
    if not url:
        return ""

    try:
        html = fetch_html_retry(url, timeout=timeout, tentativas=2)
        if safe_str(html):
            return safe_str(html)
    except Exception:
        pass

    for headers in HEADERS_POOL:
        try:
            response = session.get(
                url,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
                verify=True,
            )
            if response.ok and safe_str(response.text):
                return response.text
        except Exception:
            pass

        try:
            response = session.get(
                url,
                headers=headers,
                timeout=timeout,
                allow_redirects=True,
                verify=False,
            )
            if response.ok and safe_str(response.text):
                return response.text
        except Exception:
            pass

    return ""


def _extrair_urls_de_sitemap_xml(base_url: str, xml_text: str) -> list[str]:
    urls: list[str] = []
    vistos: set[str] = set()

    xml_text = safe_str(xml_text)
    if not xml_text:
        return urls

    try:
        root = ET.fromstring(xml_text.encode("utf-8"))
        for loc in root.iter():
            tag = safe_str(loc.tag).lower()
            if not tag.endswith("loc"):
                continue
            valor = normalizar_link_crawl(base_url, safe_str(loc.text))
            if not valor or valor in vistos:
                continue
            if not url_valida_para_crawl(base_url, valor):
                continue
            vistos.add(valor)
            urls.append(valor)
    except Exception:
        for match in re.findall(r"<loc>\s*([^<]+)\s*</loc>", xml_text, flags=re.I):
            valor = normalizar_link_crawl(base_url, match)
            if valor and valor not in vistos and url_valida_para_crawl(base_url, valor):
                vistos.add(valor)
                urls.append(valor)

    return urls


def _buscar_sitemaps(session: requests.Session, base_url: str, max_sitemaps: int = 30) -> list[str]:
    raiz = _raiz(base_url)
    candidatos = [f"{raiz}{path}" for path in SITEMAP_PATHS]
    fila = deque(candidatos)
    visitados: set[str] = set()
    urls: list[str] = []
    vistos_urls: set[str] = set()

    while fila and len(visitados) < max_sitemaps:
        sitemap_url = fila.popleft()
        if sitemap_url in visitados:
            continue

        visitados.add(sitemap_url)
        xml_text = _fetch(session, sitemap_url, timeout=25)
        if not xml_text:
            continue

        encontrados = _extrair_urls_de_sitemap_xml(base_url, xml_text)

        for item in encontrados:
            item_n = normalizar_texto(item)

            if item_n.endswith(".xml") or "sitemap" in item_n and item_n not in visitados:
                fila.append(item)
                continue

            if item not in vistos_urls:
                vistos_urls.add(item)
                urls.append(item)

    return urls


def _extrair_links_js(base_url: str, html: str) -> list[str]:
    html = safe_str(html)
    if not html:
        return []

    padroes = [
        r"https?://[^\"'<>\\\s]+",
        r"\\/produto\\/[^\"'<>\\\s]+",
        r"\\/produtos\\/[^\"'<>\\\s]+",
        r"\\/product\\/[^\"'<>\\\s]+",
        r"\\/products\\/[^\"'<>\\\s]+",
        r"\\/p\\/[^\"'<>\\\s]+",
        r"\\/item\\/[^\"'<>\\\s]+",
        r"\\/sku\\/[^\"'<>\\\s]+",
    ]

    saida: list[str] = []
    vistos: set[str] = set()

    for padrao in padroes:
        for raw in re.findall(padrao, html, flags=re.I):
            raw = safe_str(raw).replace("\\/", "/")
            url = normalizar_link_crawl(base_url, raw)
            if not url or url in vistos:
                continue
            if not url_valida_para_crawl(base_url, url):
                continue
            if _url_ruim(url):
                continue
            vistos.add(url)
            saida.append(url)

    return saida


def _descobrir_links_por_bfs(
    session: requests.Session,
    base_url: str,
    *,
    max_paginas: int,
    max_produtos: int,
    max_segundos: int,
) -> list[str]:
    inicio = time.time()
    base_url = normalizar_url(base_url)
    fila = deque([base_url, _raiz(base_url)])
    visitados: set[str] = set()
    produtos: list[str] = []
    produtos_vistos: set[str] = set()

    while fila:
        if len(visitados) >= max_paginas:
            break
        if len(produtos) >= max_produtos:
            break
        if time.time() - inicio > max_segundos:
            break

        pagina = fila.popleft()
        if pagina in visitados:
            continue

        visitados.add(pagina)

        html = _fetch(session, pagina)
        if not html:
            continue

        if _html_tem_produto(html) and not _parece_categoria_url(pagina):
            if pagina not in produtos_vistos:
                produtos_vistos.add(pagina)
                produtos.append(pagina)

        try:
            links_categoria, links_produto = extrair_links_pagina(base_url, pagina, html)
        except Exception:
            links_categoria, links_produto = [], []

        links_js = _extrair_links_js(base_url, html)

        for link in links_produto + links_js:
            if not link or link in produtos_vistos:
                continue
            if not _mesmo_host(base_url, link):
                continue
            if _url_ruim(link):
                continue

            if _parece_produto_url(link) or not _parece_categoria_url(link):
                produtos_vistos.add(link)
                produtos.append(link)

            if len(produtos) >= max_produtos:
                break

        for link in links_categoria:
            if not link:
                continue
            if link in visitados or link in fila:
                continue
            if not _mesmo_host(base_url, link):
                continue
            if _url_ruim(link):
                continue
            fila.append(link)

        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            href = normalizar_link_crawl(base_url, safe_str(a.get("href")))
            if not href:
                continue
            if href in visitados or href in fila:
                continue
            if not _mesmo_host(base_url, href):
                continue
            if _url_ruim(href):
                continue

            texto = safe_str(a.get_text(" ", strip=True))
            contexto = normalizar_texto(f"{href} {texto}")

            if _parece_produto_url(href):
                if href not in produtos_vistos:
                    produtos_vistos.add(href)
                    produtos.append(href)
            elif _parece_categoria_url(href) or any(x in contexto for x in ("produtos", "categoria", "departamento", "ver mais")):
                fila.append(href)

    return produtos[:max_produtos]


def _descobrir_links_produtos(
    session: requests.Session,
    base_url: str,
    *,
    usar_sitemap: bool,
    usar_home: bool,
    max_paginas: int,
    max_produtos: int,
    max_segundos: int,
    auth_context: dict[str, Any] | None,
) -> list[str]:
    encontrados: list[str] = []
    vistos: set[str] = set()

    def add_many(lista: list[str]) -> None:
        for url in lista:
            url = normalizar_link_crawl(base_url, url)
            if not url or url in vistos:
                continue
            if not url_valida_para_crawl(base_url, url):
                continue
            if _url_ruim(url):
                continue
            vistos.add(url)
            encontrados.append(url)

    if usar_sitemap:
        _log("[CRAWLER_ENGINE] Lendo sitemap.")
        sitemap_urls = _buscar_sitemaps(session, base_url)
        produtos_sitemap = [u for u in sitemap_urls if _parece_produto_url(u)]
        add_many(produtos_sitemap)

    if len(encontrados) < max_produtos and usar_home:
        _log("[CRAWLER_ENGINE] Lendo home, categorias, paginações e JS.")
        try:
            descobertos = descobrir_produtos_no_dominio(
                base_url,
                max_paginas=max_paginas,
                max_produtos=max_produtos,
                max_segundos=max_segundos,
                auth_context=auth_context,
            )
            add_many(descobertos)
        except Exception as exc:
            _log(f"[CRAWLER_ENGINE] descoberta via links module falhou: {exc}")

    if len(encontrados) < max_produtos and usar_home:
        try:
            bfs = _descobrir_links_por_bfs(
                session,
                base_url,
                max_paginas=max_paginas,
                max_produtos=max_produtos,
                max_segundos=max_segundos,
            )
            add_many(bfs)
        except Exception as exc:
            _log(f"[CRAWLER_ENGINE] BFS fallback falhou: {exc}")

    if not encontrados:
        html = _fetch(session, base_url)
        if html and _html_tem_produto(html):
            add_many([base_url])

    return encontrados[:max_produtos]


def _produto_valido(produto: dict[str, Any]) -> bool:
    nome = safe_str(produto.get("descricao") or produto.get("nome"))
    url = safe_str(produto.get("url_produto"))
    preco = safe_str(produto.get("preco"))
    imagens = safe_str(produto.get("url_imagens") or produto.get("imagens"))
    codigo = safe_str(produto.get("codigo") or produto.get("sku"))
    gtin = safe_str(produto.get("gtin"))

    score = 0
    if nome and len(nome) >= 4:
        score += 3
    if url:
        score += 1
    if preco:
        score += 2
    if imagens:
        score += 1
    if codigo:
        score += 1
    if gtin:
        score += 1

    return score >= 3


def _extrair_um_produto(session: requests.Session, url_produto: str) -> dict[str, Any]:
    html = _fetch(session, url_produto)
    if not html:
        return {}

    produto = extrair_detalhes_heuristicos(url_produto, html)
    if not isinstance(produto, dict):
        return {}

    produto.setdefault("url_produto", url_produto)

    if not safe_str(produto.get("descricao")):
        soup = BeautifulSoup(html, "lxml")
        titulo = safe_str(
            soup.select_one("h1").get_text(" ", strip=True)
            if soup.select_one("h1")
            else ""
        )
        if titulo:
            produto["descricao"] = titulo

    return produto if _produto_valido(produto) else {}


def _normalizar_saida(produtos: list[dict[str, Any]]) -> pd.DataFrame:
    linhas: list[dict[str, Any]] = []

    for p in produtos:
        if not isinstance(p, dict):
            continue

        linha = {
            "url_produto": safe_str(p.get("url_produto")),
            "nome": safe_str(p.get("descricao") or p.get("nome")),
            "sku": safe_str(p.get("codigo") or p.get("sku")),
            "marca": safe_str(p.get("marca")),
            "categoria": safe_str(p.get("categoria")),
            "estoque": safe_str(p.get("quantidade") or p.get("estoque") or "1"),
            "preco": safe_str(p.get("preco")),
            "gtin": re.sub(r"\D+", "", safe_str(p.get("gtin"))),
            "descricao": safe_str(p.get("descricao_detalhada") or p.get("descricao")),
            "imagens": safe_str(p.get("url_imagens") or p.get("imagens")),
        }

        if linha["gtin"] and len(linha["gtin"]) not in (8, 12, 13, 14):
            linha["gtin"] = ""

        if linha["nome"] or linha["url_produto"]:
            linhas.append(linha)

    df = pd.DataFrame(linhas)

    colunas = [
        "url_produto",
        "nome",
        "sku",
        "marca",
        "categoria",
        "estoque",
        "preco",
        "gtin",
        "descricao",
        "imagens",
    ]

    for col in colunas:
        if col not in df.columns:
            df[col] = ""

    if df.empty:
        return df[colunas]

    df["_dedupe"] = (
        df["url_produto"].astype(str).str.strip().str.lower()
        + "|"
        + df["sku"].astype(str).str.strip().str.lower()
        + "|"
        + df["nome"].astype(str).str.strip().str.lower()
    )
    df = df.drop_duplicates(subset=["_dedupe"], keep="first")
    df = df.drop(columns=["_dedupe"], errors="ignore")

    return df[colunas].reset_index(drop=True)


def run_crawler(
    base_url: str,
    *,
    auth_context: dict[str, Any] | None = None,
    varrer_site_completo: bool = True,
    sitemap_completo: bool = True,
    max_workers: int = 12,
    limite: int | None = None,
    limite_paginas: int | None = None,
    usar_sitemap: bool = True,
    usar_home: bool = True,
    usar_categoria: bool = True,
    modo: str = "completo",
    preferir_playwright: bool = False,
    **kwargs: Any,
) -> pd.DataFrame:
    """
    Entrada principal usada pelo SiteAgent.

    Observação:
    preferir_playwright é aceito por compatibilidade, mas este engine não depende dele.
    """

    inicio = time.time()
    url = normalizar_url(base_url)

    if not url:
        return pd.DataFrame(
            columns=[
                "url_produto",
                "nome",
                "sku",
                "marca",
                "categoria",
                "estoque",
                "preco",
                "gtin",
                "descricao",
                "imagens",
            ]
        )

    max_workers = max(1, min(int(max_workers or 8), 24))

    if limite is None:
        limite_produtos = 8000 if varrer_site_completo else 300
    else:
        try:
            limite_produtos = max(1, int(limite))
        except Exception:
            limite_produtos = 8000 if varrer_site_completo else 300

    if limite_paginas is None:
        max_paginas = 600 if varrer_site_completo else 80
    else:
        try:
            max_paginas = max(1, int(limite_paginas))
        except Exception:
            max_paginas = 600 if varrer_site_completo else 80

    max_segundos = int(kwargs.get("max_segundos", 900 if varrer_site_completo else 240))

    session = _criar_session(auth_context)

    _log(
        "[CRAWLER_ENGINE] Iniciado "
        f"| modo=http_hybrid_sem_playwright "
        f"| url={url} "
        f"| sitemap={usar_sitemap and sitemap_completo} "
        f"| home={usar_home} "
        f"| max_paginas={max_paginas} "
        f"| limite_produtos={limite_produtos} "
        f"| workers={max_workers}"
    )

    links = _descobrir_links_produtos(
        session,
        url,
        usar_sitemap=bool(usar_sitemap and sitemap_completo),
        usar_home=bool(usar_home or usar_categoria),
        max_paginas=max_paginas,
        max_produtos=limite_produtos,
        max_segundos=max_segundos,
        auth_context=auth_context,
    )

    links = links[:limite_produtos]
    _log(f"[CRAWLER_ENGINE] Links de produto candidatos: {len(links)}")

    produtos: list[dict[str, Any]] = []

    if not links:
        html_home = _fetch(session, url)
        if html_home:
            direto = extrair_detalhes_heuristicos(url, html_home)
            if isinstance(direto, dict) and _produto_valido(direto):
                produtos.append(direto)

        df_vazio_ou_direto = _normalizar_saida(produtos)
        _log(f"[CRAWLER_ENGINE] Finalizado com {len(df_vazio_ou_direto)} produto(s).")
        return df_vazio_ou_direto

    def worker(link: str) -> dict[str, Any]:
        try:
            return _extrair_um_produto(session, link)
        except Exception:
            return {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futuros = {executor.submit(worker, link): link for link in links}

        for idx, futuro in enumerate(concurrent.futures.as_completed(futuros), start=1):
            if time.time() - inicio > max_segundos:
                _log("[CRAWLER_ENGINE] Tempo máximo atingido; retornando parcial.")
                break

            try:
                produto = futuro.result()
            except Exception:
                produto = {}

            if produto:
                produtos.append(produto)

            if idx % 25 == 0:
                _log(
                    f"[CRAWLER_ENGINE] Progresso: {idx}/{len(links)} páginas lidas "
                    f"| produtos válidos={len(produtos)}"
                )

            if len(produtos) >= limite_produtos:
                break

    df = _normalizar_saida(produtos)

    _log(
        "[CRAWLER_ENGINE] Concluído "
        f"| links={len(links)} "
        f"| produtos={len(df)} "
        f"| tempo={time.time() - inicio:.1f}s"
    )

    return df
