from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

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

# ==========================================================
# LOG (BLINDADO)
# ==========================================================
try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    try:
        from bling_app_zero.utils.excel import log_debug
    except Exception:
        def log_debug(*args, **kwargs):
            pass


# ==========================================================
# COLETA PAGINAÇÃO
# ==========================================================
def _coletar_paginas_listagem(
    url_inicial: str,
    max_paginas: int = MAX_PAGINAS,
) -> list[str]:

    visitadas = set()
    fila = [url_inicial]
    saida = []

    log_debug(f"[CRAWLER] Iniciando paginação: {url_inicial}")

    while fila and len(saida) < max_paginas:
        url = fila.pop(0)

        if not url or url in visitadas:
            continue

        visitadas.add(url)

        html = fetch_url(url)
        if not html:
            log_debug(f"[CRAWLER] Falha ao carregar página: {url}", "WARNING")
            continue

        log_debug(f"[CRAWLER] Página coletada: {url}")

        saida.append(url)

        try:
            novos_links = extrair_links_paginacao_crawler(html, url)
        except Exception as e:
            log_debug(f"[CRAWLER] Erro extraindo paginação: {url} | {e}", "ERROR")
            continue

        for prox in novos_links:
            if (
                prox
                and prox not in visitadas
                and prox not in fila
                and len(saida) + len(fila) < max_paginas
            ):
                fila.append(prox)

    log_debug(f"[CRAWLER] Total páginas coletadas: {len(saida)}")
    return saida


# ==========================================================
# COLETA LINKS PRODUTOS
# ==========================================================
def _coletar_links_de_todas_paginas(
    url_inicial: str,
    max_paginas: int = MAX_PAGINAS,
) -> list[str]:

    paginas = _coletar_paginas_listagem(url_inicial, max_paginas=max_paginas)
    todos_links: list[str] = []

    for pagina in paginas:
        html = fetch_url(pagina)
        if not html:
            log_debug(f"[CRAWLER] Falha ao carregar página (links): {pagina}", "WARNING")
            continue

        try:
            links = extrair_links_produtos_crawler(html, pagina)
            log_debug(f"[CRAWLER] {len(links)} links encontrados em {pagina}")
            todos_links.extend(links)
        except Exception as e:
            log_debug(f"[CRAWLER] Erro extraindo links: {pagina} | {e}", "ERROR")

    # remover duplicados mantendo ordem
    unicos = []
    vistos = set()

    for link in todos_links:
        if link not in vistos:
            vistos.add(link)
            unicos.append(link)

    log_debug(f"[CRAWLER] Total links únicos: {len(unicos)}")

    return unicos[:MAX_PRODUTOS]


# ==========================================================
# EXTRAÇÃO PRODUTO
# ==========================================================
def _baixar_e_extrair(
    link: str,
    padrao_disponivel: int = 10,
) -> dict | None:

    html = fetch_url(link)

    if not html:
        log_debug(f"[CRAWLER] Falha ao baixar produto: {link}", "WARNING")
        return None

    try:
        produto = extrair_produto_crawler(
            html,
            link,
            padrao_disponivel=padrao_disponivel,
        )
    except Exception as e:
        log_debug(f"[CRAWLER] Erro ao extrair produto: {link} | {e}", "ERROR")
        return None

    if not produto.get("Nome"):
        log_debug(f"[CRAWLER] Produto inválido (sem nome): {link}", "WARNING")
        return None

    return produto


# ==========================================================
# EXECUÇÃO PRINCIPAL
# ==========================================================
def executar_crawler(
    url: str,
    max_paginas: int = MAX_PAGINAS,
    max_threads: int = MAX_THREADS,
    padrao_disponivel: int = 10,
) -> pd.DataFrame:

    if not url:
        log_debug("[CRAWLER] URL vazia", "ERROR")
        return pd.DataFrame()

    log_debug(f"[CRAWLER] INÍCIO → {url}")

    links = _coletar_links_de_todas_paginas(url, max_paginas=max_paginas)

    # ======================================================
    # FALLBACK → página única
    # ======================================================
    if not links:
        log_debug("[CRAWLER] Nenhum link encontrado → fallback página única")

        html_unico = fetch_url(url)

        if html_unico:
            try:
                produto = extrair_produto_crawler(
                    html_unico,
                    url,
                    padrao_disponivel=padrao_disponivel,
                )

                if produto.get("Nome"):
                    log_debug("[CRAWLER] Produto único extraído com sucesso")
                    return pd.DataFrame([produto])

            except Exception as e:
                log_debug(f"[CRAWLER] Erro fallback produto único | {e}", "ERROR")

        log_debug("[CRAWLER] Falha total no fallback", "ERROR")
        return pd.DataFrame()

    # ======================================================
    # DOWNLOAD PARALELO
    # ======================================================
    resultados: list[dict] = []

    log_debug(f"[CRAWLER] Iniciando download paralelo ({len(links)} links)")

    with ThreadPoolExecutor(max_workers=max_threads) as executor:

        futuros = {
            executor.submit(_baixar_e_extrair, link, padrao_disponivel): link
            for link in links
        }

        for i, futuro in enumerate(as_completed(futuros), start=1):
            link = futuros[futuro]

            try:
                produto = futuro.result()

                if produto:
                    resultados.append(produto)

                if i % 10 == 0:
                    log_debug(f"[CRAWLER] Progresso: {i}/{len(links)}")

            except Exception as e:
                log_debug(f"[CRAWLER] Erro thread: {link} | {e}", "ERROR")

    if not resultados:
        log_debug("[CRAWLER] Nenhum produto válido encontrado", "ERROR")
        return pd.DataFrame()

    df = pd.DataFrame(resultados)

    # ======================================================
    # LIMPEZA
    # ======================================================
    if "Link Externo" in df.columns:
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

    log_debug(f"[CRAWLER] FINALIZADO → {len(df)} produtos válidos")

    return df.reset_index(drop=True)
