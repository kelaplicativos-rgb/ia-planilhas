from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from bling_app_zero.core.fetcher import fetch_url
from bling_app_zero.core.site_crawler_extractors import extrair_produto_crawler
from bling_app_zero.core.site_crawler_helpers import (
    MAX_PAGINAS,
    MAX_PRODUTOS,
    MAX_THREADS,
    extrair_links_paginacao_crawler,
    extrair_links_produtos_crawler,
)


def _coletar_paginas_listagem(
    url_inicial: str,
    max_paginas: int = MAX_PAGINAS,
) -> list[str]:
    visitadas = set()
    fila = [url_inicial]
    saida = []

    while fila and len(saida) < max_paginas:
        url = fila.pop(0)
        if not url or url in visitadas:
            continue

        visitadas.add(url)
        html = fetch_url(url)
        if not html:
            continue

        saida.append(url)

        for prox in extrair_links_paginacao_crawler(html, url):
            if prox not in visitadas and prox not in fila and len(saida) + len(fila) < max_paginas:
                fila.append(prox)

    return saida


def _coletar_links_de_todas_paginas(
    url_inicial: str,
    max_paginas: int = MAX_PAGINAS,
) -> list[str]:
    paginas = _coletar_paginas_listagem(url_inicial, max_paginas=max_paginas)
    todos_links: list[str] = []

    for pagina in paginas:
        html = fetch_url(pagina)
        if not html:
            continue
        todos_links.extend(extrair_links_produtos_crawler(html, pagina))

    unicos = []
    for link in todos_links:
        if link not in unicos:
            unicos.append(link)

    return unicos[:MAX_PRODUTOS]


def _baixar_e_extrair(
    link: str,
    padrao_disponivel: int = 10,
) -> dict | None:
    html = fetch_url(link)
    if not html:
        return None

    produto = extrair_produto_crawler(
        html,
        link,
        padrao_disponivel=padrao_disponivel,
    )
    if not produto.get("Nome"):
        return None
    return produto


def executar_crawler(
    url: str,
    max_paginas: int = MAX_PAGINAS,
    max_threads: int = MAX_THREADS,
    padrao_disponivel: int = 10,
) -> pd.DataFrame:
    if not url:
        return pd.DataFrame()

    links = _coletar_links_de_todas_paginas(url, max_paginas=max_paginas)

    if not links:
        html_unico = fetch_url(url)
        if html_unico:
            produto = extrair_produto_crawler(
                html_unico,
                url,
                padrao_disponivel=padrao_disponivel,
            )
            if produto.get("Nome"):
                return pd.DataFrame([produto])
        return pd.DataFrame()

    resultados: list[dict] = []

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futuros = {
            executor.submit(_baixar_e_extrair, link, padrao_disponivel): link
            for link in links
        }

        for futuro in as_completed(futuros):
            try:
                produto = futuro.result()
                if produto:
                    resultados.append(produto)
            except Exception:
                continue

    if not resultados:
        return pd.DataFrame()

    df = pd.DataFrame(resultados)
    df = df.drop_duplicates(subset=["Link Externo"], keep="first")

    for col in [
        "Nome",
        "Preço",
        "Descrição",
        "Descrição Curta",
        "Marca",
        "Categoria",
        "GTIN/EAN",
        "NCM",
        "URL Imagens Externas",
        "Link Externo",
        "Estoque",
    ]:
        if col not in df.columns:
            df[col] = ""

    return df.reset_index(drop=True)
