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


# 🔥 CORREÇÃO CRÍTICA → FORÇA JS SEMPRE
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

        payload = _fetch(url)  # 🔥 sempre JS
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
# LINKS PRODUTOS
# ==========================================================
def _coletar_links(url: str, max_paginas: int) -> list[str]:

    paginas = _coletar_paginas_listagem(url, max_paginas)
    links = []

    for p in paginas:
        payload = _fetch(p)  # 🔥 sempre JS
        html = payload.get("html")

        if not html:
            continue

        try:
            links.extend(extrair_links_produtos_crawler(html, p))
        except Exception:
            pass

    return list(dict.fromkeys(links))[:MAX_PRODUTOS]


# ==========================================================
# EXTRAÇÃO
# ==========================================================
def _baixar(link: str, padrao: int) -> dict | None:

    payload = _fetch(link)  # 🔥 sempre JS
    html = payload.get("html")

    if not html:
        return None

    try:
        produto = extrair_produto_crawler(
            html=html,
            url=link,
            padrao_disponivel=padrao,
            network_records=_safe_list(payload.get("network_records")),
            payload_origem=payload,
        )
    except Exception:
        return None

    return produto if produto.get("Nome") else None


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

    status.info("🔎 Coletando links...")

    links = _coletar_links(url, max_paginas)

    status.info(f"🔗 {len(links)} produtos encontrados. Iniciando extração...")

    # 🔥 fallback produto único
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

    resultados = []
    total = len(links)

    with ThreadPoolExecutor(max_workers=max_threads) as ex:
        futs = {ex.submit(_baixar, l, padrao_disponivel): l for l in links}

        for i, f in enumerate(as_completed(futs), start=1):
            r = f.result()

            if r:
                resultados.append(r)

            progresso = int((i / total) * 100)
            progress_bar.progress(progresso)

            status.info(f"⚙️ Processando: {i}/{total} ({progresso}%)")

    if not resultados:
        status.error("❌ Nenhum produto válido encontrado")
        return pd.DataFrame()

    df = pd.DataFrame(resultados)

    if "Link Externo" in df.columns:
        df = df.drop_duplicates(subset=["Link Externo"])

    progress_bar.progress(100)
    status.success(f"✅ Finalizado: {len(df)} produtos")

    return df.reset_index(drop=True)
