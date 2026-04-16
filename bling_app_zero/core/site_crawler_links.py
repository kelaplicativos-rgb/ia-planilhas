
from __future__ import annotations

import re
import time
from collections import deque
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from bling_app_zero.core.site_crawler_cleaners import (
    extrair_preco,
    fornecedor_cfg,
    normalizar_texto,
    normalizar_url,
    safe_str,
)
from bling_app_zero.core.site_crawler_config import ROTAS_INICIAIS_PADRAO
from bling_app_zero.core.site_crawler_http import (
    fetch_html_retry,
    normalizar_link_crawl,
    url_valida_para_crawl,
)


def classificar_link(base_url: str, url: str, texto_ancora: str = "", bloco: str = "") -> str:
    cfg = fornecedor_cfg(base_url)
    url_n = normalizar_texto(url)
    texto_n = normalizar_texto(texto_ancora)
    bloco_n = normalizar_texto(bloco)

    hints_produto = cfg.get(
        "produto_hints",
        ["/produto", "/product", "/p/", "/item/", "/sku/", "/prd/"],
    )
    hints_categoria = cfg.get(
        "categoria_hints",
        ["/categoria", "/categorias", "/collections/", "/departamento", "/busca", "/search"],
    )

    score_produto = 0
    score_categoria = 0

    if any(h in url_n for h in hints_produto):
        score_produto += 4

    if any(h in url_n for h in hints_categoria):
        score_categoria += 4

    if re.search(r"/p/\d+|/produto/|/product/|/sku/|/item/", url_n):
        score_produto += 3

    if re.search(r"/categoria/|/categorias/|/collections?/|/departamentos?/", url_n):
        score_categoria += 3

    if any(t in texto_n for t in ["comprar", "ver produto", "detalhes", "sku", "código", "codigo"]):
        score_produto += 2

    if any(t in texto_n for t in ["categoria", "departamento", "coleção", "colecao", "produtos"]):
        score_categoria += 2

    if extrair_preco(bloco_n):
        score_produto += 1

    if any(t in bloco_n for t in ["adicionar ao carrinho", "comprar agora", "parcel", "r$"]):
        score_produto += 1

    if "page=" in url_n or "/page/" in url_n or "p=" in url_n:
        score_categoria += 2

    if score_produto >= max(3, score_categoria):
        return "produto"

    if score_categoria >= 2:
        return "categoria"

    return "indefinido"


def eh_paginacao(url: str, texto: str = "") -> bool:
    url_n = normalizar_texto(url)
    texto_n = normalizar_texto(texto)

    if any(x in url_n for x in ["page=", "/page/", "?p=", "&p="]):
        return True

    if re.search(r"/page/\d+", url_n):
        return True

    if texto_n in {"1", "2", "3", "4", "5", "próxima", "proxima", "next", ">", ">>"}:
        return True

    if any(x in texto_n for x in ["próxima", "proxima", "next", "avançar", "avancar"]):
        return True

    return False


def extrair_produtos_de_cards(base_url: str, soup: BeautifulSoup) -> list[str]:
    links_produto = []
    vistos = set()

    seletores_cards = [
        "[class*='product']",
        "[class*='produto']",
        "[class*='item']",
        "[class*='card']",
        "li",
        "article",
        "div",
    ]

    for seletor in seletores_cards:
        try:
            cards = soup.select(seletor)
        except Exception:
            cards = []

        for card in cards:
            try:
                bloco = card.get_text(" ", strip=True)[:1500]
            except Exception:
                bloco = ""

            bloco_n = normalizar_texto(bloco)
            if not bloco_n:
                continue

            possui_sinal_produto = False

            if extrair_preco(bloco):
                possui_sinal_produto = True

            if any(
                x in bloco_n
                for x in [
                    "comprar",
                    "carrinho",
                    "adicionar",
                    "parcel",
                    "sku",
                    "código",
                    "codigo",
                    "produto",
                ]
            ):
                possui_sinal_produto = True

            if not possui_sinal_produto:
                continue

            anchors = card.select("a[href]")
            for a in anchors:
                href = safe_str(a.get("href"))
                url = normalizar_link_crawl(base_url, href)
                if not url_valida_para_crawl(base_url, url):
                    continue

                texto = " ".join(a.stripped_strings).strip()
                classe = classificar_link(base_url, url, texto, bloco)

                if classe == "produto" or possui_sinal_produto:
                    if url not in vistos:
                        vistos.add(url)
                        links_produto.append(url)

    return links_produto


def extrair_links_pagina(base_url: str, url_pagina: str, html: str) -> tuple[list[str], list[str]]:
    soup = BeautifulSoup(html, "lxml")

    links_categoria = []
    links_produto = []
    vistos_categoria = set()
    vistos_produto = set()

    produtos_card = extrair_produtos_de_cards(base_url, soup)
    for url in produtos_card:
        if url not in vistos_produto:
            vistos_produto.add(url)
            links_produto.append(url)

    for a in soup.find_all("a", href=True):
        href = safe_str(a.get("href"))
        if not href:
            continue

        url = normalizar_link_crawl(base_url, href)
        if not url_valida_para_crawl(base_url, url):
            continue

        texto = " ".join(a.stripped_strings).strip()
        bloco = ""
        try:
            bloco = a.parent.get_text(" ", strip=True)[:1200]
        except Exception:
            bloco = texto

        if eh_paginacao(url, texto):
            if url not in vistos_categoria:
                vistos_categoria.add(url)
                links_categoria.append(url)
            continue

        classe = classificar_link(base_url, url, texto, bloco)

        possui_sinal_produto = (
            bool(extrair_preco(bloco))
            or any(
                x in normalizar_texto(bloco)
                for x in ["r$", "comprar", "carrinho", "parcel", "sku", "código", "codigo"]
            )
        )

        if classe == "produto" or possui_sinal_produto:
            if url not in vistos_produto:
                vistos_produto.add(url)
                links_produto.append(url)
            continue

        if classe == "categoria":
            if url not in vistos_categoria:
                vistos_categoria.add(url)
                links_categoria.append(url)
            continue

        if url not in vistos_categoria:
            vistos_categoria.add(url)
            links_categoria.append(url)

    if url_pagina not in vistos_categoria and classificar_link(base_url, url_pagina) == "categoria":
        links_categoria.insert(0, url_pagina)

    return links_categoria, links_produto


def rotas_iniciais(base_url: str, termo: str = "") -> list[str]:
    base = normalizar_url(base_url)
    urls = [f"{base}{rota}" for rota in ROTAS_INICIAIS_PADRAO]

    termo = safe_str(termo)
    if termo:
        q = quote_plus(termo)
        slug = re.sub(r"[^a-z0-9]+", "-", normalizar_texto(termo)).strip("-")
        urls.extend(
            [
                f"{base}/search?q={q}",
                f"{base}/busca?q={q}",
                f"{base}/busca?search={q}",
                f"{base}/catalogsearch/result/?q={q}",
                f"{base}/categoria/{slug}",
                f"{base}/?s={q}",
            ]
        )

    vistos = set()
    saida = []
    for url in urls:
        url = normalizar_link_crawl(base, url)
        if url and url not in vistos:
            vistos.add(url)
            saida.append(url)

    return saida


def descobrir_produtos_no_dominio(
    base_url: str,
    termo: str = "",
    max_paginas: int = 400,
    max_produtos: int = 8000,
    max_segundos: int = 900,
) -> list[str]:
    inicio = time.time()

    fila = deque(rotas_iniciais(base_url, termo=termo))
    paginas_visitadas = set()
    produtos_encontrados = []
    produtos_vistos = set()

    while fila:
        if len(paginas_visitadas) >= max_paginas:
            break
        if len(produtos_encontrados) >= max_produtos:
            break
        if time.time() - inicio > max_segundos:
            break

        url_atual = fila.popleft()
        if url_atual in paginas_visitadas:
            continue

        paginas_visitadas.add(url_atual)

        try:
            html = fetch_html_retry(url_atual, tentativas=2)
        except Exception:
            continue

        links_categoria, links_produto = extrair_links_pagina(base_url, url_atual, html)

        for url_produto in links_produto:
            if url_produto not in produtos_vistos:
                produtos_vistos.add(url_produto)
                produtos_encontrados.append(url_produto)
                if len(produtos_encontrados) >= max_produtos:
                    break

        for url_categoria in links_categoria:
            if url_categoria not in paginas_visitadas and url_categoria not in fila:
                fila.append(url_categoria)

    return produtos_encontrados
