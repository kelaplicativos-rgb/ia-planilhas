from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pandas as pd
import streamlit as st

from bling_app_zero.core.fetch_router import fetch_payload_router

from bling_app_zero.core.site_crawler_extractors import extrair_produto_crawler
from bling_app_zero.core.site_crawler_helpers import (
    MAX_PAGINAS,
    MAX_PRODUTOS,
    MAX_THREADS,
    extrair_links_paginacao_crawler,
    extrair_links_produtos_crawler,
)

# ==========================================================
# LOG
# ==========================================================
try:
    from bling_app_zero.utils.excel_logs import log_debug
except Exception:
    def log_debug(*args, **kwargs):
        pass


# ==========================================================
# SAFE
# ==========================================================
def _safe_list(v: Any) -> list:
    return v if isinstance(v, list) else []


# 🔥 FORÇA JS
def _fetch(url: str, js: bool = True) -> dict:
    try:
        return fetch_payload_router(url=url, preferir_js=True) or {}
    except Exception as e:
        log_debug(f"[CRAWLER] Erro fetch: {url} | {e}", "ERROR")
        return {}


# ==========================================================
# PAGINAÇÃO
# ==========================================================
def _coletar_paginas_listagem(url_inicial: str, max_paginas: int) -> list[str]:

    visitadas = set()
    fila = [url_inicial]
    saida = []

    while fila and len(saida) < max_paginas:
        url = fila.pop(0)

        if not url or url in visitadas:
            continue

        visitadas.add(url)

        payload = _fetch(url)
        html = payload.get("html")

        if not html:
            continue

        saida.append(url)

        try:
            novos = extrair_links_paginacao_crawler(html, url)
            fila.extend([n for n in novos if n not in visitadas])
        except Exception:
            pass

    return saida


# ==========================================================
# MAIN
# ==========================================================
def executar_crawler(
    url: str,
    max_paginas: int = MAX_PAGINAS,
    max_threads: int = MAX_THREADS,
    padrao_disponivel: int = 10,
) -> pd.DataFrame:

    if not url:
        return pd.DataFrame()

    progress_bar = st.progress(0)
    status = st.empty()
    detalhe = st.empty()

    # ======================================================
    # ETAPA 1 - PÁGINAS
    # ======================================================
    status.info("🔎 Buscando páginas do site...")
    progress_bar.progress(5)

    paginas = _coletar_paginas_listagem(url, max_paginas)

    status.info(f"📄 {len(paginas)} páginas encontradas")
    progress_bar.progress(15)

    # ======================================================
    # ETAPA 2 - LINKS
    # ======================================================
    links = []

    for i, p in enumerate(paginas, start=1):
        detalhe.info(f"🔗 Lendo página {i}/{len(paginas)}")

        payload = _fetch(p)
        html = payload.get("html")

        if html:
            try:
                novos = extrair_links_produtos_crawler(html, p)
                links.extend(novos)
            except Exception:
                pass

        progresso = 15 + int((i / max(len(paginas), 1)) * 25)
        progress_bar.progress(progresso)

    links = list(dict.fromkeys(links))[:MAX_PRODUTOS]

    status.info(f"🔗 {len(links)} produtos encontrados")
    progress_bar.progress(40)

    # ======================================================
    # FALLBACK
    # ======================================================
    if not links:
        status.warning("⚠️ Nenhum link encontrado, tentando página única...")

        payload = _fetch(url)
        html = payload.get("html")

        if html:
            produto = extrair_produto_crawler(
                html=html,
                url=url,
                padrao_disponivel=padrao_disponivel,
                network_records=_safe_list(payload.get("network_records")),
                payload_origem=payload,
            )
            if produto.get("Nome"):
                progress_bar.progress(100)
                status.success("✅ Produto único extraído")
                return pd.DataFrame([produto])

        status.error("❌ Falha total")
        return pd.DataFrame()

    # ======================================================
    # ETAPA 3 - EXTRAÇÃO
    # ======================================================
    status.info("📦 Extraindo produtos...")
    progress_bar.progress(45)

    resultados = []
    total = len(links)

    with ThreadPoolExecutor(max_workers=max_threads) as ex:
        futs = {ex.submit(_baixar, l, padrao_disponivel): l for l in links}

        for i, f in enumerate(as_completed(futs), start=1):
            r = f.result()

            if r:
                resultados.append(r)

            progresso = 45 + int((i / total) * 50)
            progress_bar.progress(progresso)

            detalhe.info(
                f"⚙️ Processando produto {i}/{total} ({int((i/total)*100)}%)"
            )

    # ======================================================
    # FINAL
    # ======================================================
    if not resultados:
        status.error("❌ Nenhum produto válido encontrado")
        return pd.DataFrame()

    df = pd.DataFrame(resultados)

    if "Link Externo" in df.columns:
        df = df.drop_duplicates(subset=["Link Externo"])

    progress_bar.progress(100)
    status.success(f"✅ Finalizado: {len(df)} produtos extraídos")

    return df.reset_index(drop=True)
