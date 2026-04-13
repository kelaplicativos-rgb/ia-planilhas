from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.site_crawler_extractors import extrair_produto_crawler
from bling_app_zero.core.site_crawler_helpers import MAX_PRODUTOS

from .site_crawler_links_engine import coletar_paginas_listagem, extrair_links_agressivo
from .site_crawler_shared import fetch_inteligente, log_debug, safe_list


def baixar_produto(link: str, padrao_disponivel: int) -> dict[str, Any] | None:
    payload = fetch_inteligente(link)
    html = str(payload.get("html") or "").strip()

    if not html:
        log_debug(f"[CRAWLER] Produto sem HTML: {link}", "WARNING")
        return None

    try:
        produto = extrair_produto_crawler(
            html=html,
            url=link,
            padrao_disponivel=padrao_disponivel,
            network_records=safe_list(payload.get("network_records")),
            payload_origem=payload,
        )
    except Exception as e:
        log_debug(f"[CRAWLER] erro extrair produto: {link} | {e}", "ERROR")
        return None

    if not isinstance(produto, dict):
        log_debug(f"[CRAWLER] retorno inválido do extractor: {link}", "WARNING")
        return None

    nome = str(produto.get("Nome") or "").strip()
    if not nome:
        log_debug(f"[CRAWLER] produto sem Nome: {link}", "WARNING")
        return None

    if not str(produto.get("Link Externo") or "").strip():
        produto["Link Externo"] = link

    return produto


def deduplicar_links(links: list[str], limite: int = MAX_PRODUTOS) -> list[str]:
    dedup_links: list[str] = []
    vistos_links: set[str] = set()

    for link in links:
        if not link or link in vistos_links:
            continue
        vistos_links.add(link)
        dedup_links.append(link)

    return dedup_links[:limite]


def processar_paginas(
    paginas: list[tuple[str, str]],
    progress_bar,
    status,
    detalhe,
) -> list[str]:
    links: list[str] = []
    total_paginas = max(len(paginas), 1)

    for i, (pagina_url, html) in enumerate(paginas, start=1):
        detalhe.info(f" Página {i}/{total_paginas}")
        try:
            novos = extrair_links_agressivo(html, pagina_url)
            links.extend(novos)
            status.info(f" {len(links)} links coletados")
        except Exception as e:
            log_debug(
                f"[CRAWLER] erro ao extrair links da página {pagina_url}: {e}",
                "WARNING",
            )

        progress_bar.progress(15 + int((i / total_paginas) * 25))

    return deduplicar_links(links)


def fallback_links_direto(url: str) -> list[str]:
    payload = fetch_inteligente(url)
    html = str(payload.get("html") or "").strip()
    if not html:
        return []

    try:
        return extrair_links_agressivo(html, url)
    except Exception as e:
        log_debug(f"[CRAWLER] erro no fallback direto: {e}", "WARNING")
        return []


def extrair_resultados(
    links: list[str],
    padrao_disponivel: int,
    max_threads: int,
    progress_bar,
    status,
    detalhe,
) -> list[dict[str, Any]]:
    resultados: list[dict[str, Any]] = []
    total = len(links)

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futuros = {
            executor.submit(baixar_produto, link, padrao_disponivel): link
            for link in links
        }

        for i, futuro in enumerate(as_completed(futuros), start=1):
            link = futuros.get(futuro, "")
            try:
                resultado = futuro.result()
                if resultado:
                    resultados.append(resultado)
            except Exception as e:
                log_debug(f"[CRAWLER] erro future produto: {link} | {e}", "ERROR")

            progresso_extra = int((i / max(total, 1)) * 50)
            progress_bar.progress(min(100, 50 + progresso_extra))
            detalhe.info(f"⚙️ Produto {i}/{total}")
            status.info(f" Extraindo {i}/{total}")

    return resultados


def finalizar_dataframe(
    resultados: list[dict[str, Any]],
    progress_bar,
    status,
) -> pd.DataFrame:
    if not resultados:
        status.error("❌ Nenhum produto válido")
        log_debug("[CRAWLER] nenhum produto válido após extração", "WARNING")
        return pd.DataFrame()

    df = pd.DataFrame(resultados)

    if "Link Externo" in df.columns:
        try:
            df["Link Externo"] = df["Link Externo"].astype(str).str.strip()
            df = df.drop_duplicates(subset=["Link Externo"])
        except Exception:
            pass

    progress_bar.progress(100)
    status.success(f"✅ {len(df)} produtos extraídos")
    log_debug(f"[CRAWLER] finalizado com {len(df)} produtos", "INFO")
    return df.reset_index(drop=True)


def executar_pipeline_crawler(
    url: str,
    max_paginas: int,
    max_threads: int,
    padrao_disponivel: int,
) -> pd.DataFrame:
    progress_bar = st.progress(0)
    status = st.empty()
    detalhe = st.empty()
    progresso = 0

    def tick(valor: int, msg: str) -> None:
        nonlocal progresso
        progresso = min(100, progresso + max(0, int(valor)))
        progress_bar.progress(progresso)
        status.info(msg)

    log_debug(
        f"[CRAWLER] iniciar | url={url} | max_paginas={max_paginas} | max_threads={max_threads}",
        "INFO",
    )

    tick(5, " Iniciando crawler...")

    paginas = coletar_paginas_listagem(url, max_paginas)
    tick(10, f" {len(paginas)} páginas carregadas")

    links = processar_paginas(
        paginas=paginas,
        progress_bar=progress_bar,
        status=status,
        detalhe=detalhe,
    )

    if not links:
        status.warning("⚠️ Tentando fallback direto...")
        links = fallback_links_direto(url)

    tick(10, f" {len(links)} produtos detectados")

    if not links:
        status.error("❌ Nenhum produto encontrado")
        log_debug("[CRAWLER] nenhum link de produto encontrado", "WARNING")
        return pd.DataFrame()

    tick(5, " Extraindo produtos...")

    resultados = extrair_resultados(
        links=links,
        padrao_disponivel=padrao_disponivel,
        max_threads=max_threads,
        progress_bar=progress_bar,
        status=status,
        detalhe=detalhe,
    )

    return finalizar_dataframe(
        resultados=resultados,
        progress_bar=progress_bar,
        status=status,
  )
