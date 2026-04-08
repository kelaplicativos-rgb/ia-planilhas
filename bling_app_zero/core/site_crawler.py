from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pandas as pd
import streamlit as st
from bs4 import BeautifulSoup

from bling_app_zero.core.fetch_router import fetch_payload_router
from bling_app_zero.core.site_crawler_extractors import extrair_produto_crawler
from bling_app_zero.core.site_crawler_helpers import (
    MAX_PAGINAS,
    MAX_PRODUTOS,
    MAX_THREADS,
    extrair_links_paginacao_crawler,
    extrair_links_produtos_crawler,
    link_parece_produto_crawler,
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


# ==========================================================
# 🔥 FETCH INTELIGENTE
# ==========================================================
def _fetch(url: str) -> dict:
    try:
        payload = fetch_payload_router(url=url, preferir_js=True) or {}

        html = payload.get("html")

        if not html:
            log_debug(f"[CRAWLER] HTML vazio: {url}", "WARNING")

        return payload

    except Exception as e:
        log_debug(f"[CRAWLER] Erro fetch: {url} | {e}", "ERROR")
        return {}


# ==========================================================
# BAIXAR PRODUTO
# ==========================================================
def _baixar(link: str, padrao_disponivel: int) -> dict | None:
    payload = _fetch(link)
    html = payload.get("html")

    if not html:
        return None

    try:
        produto = extrair_produto_crawler(
            html=html,
            url=link,
            padrao_disponivel=padrao_disponivel,
            network_records=_safe_list(payload.get("network_records")),
            payload_origem=payload,
        )
    except Exception as e:
        log_debug(f"[CRAWLER] erro extrair produto: {e}", "ERROR")
        return None

    if not produto or not produto.get("Nome"):
        return None

    return produto


# ==========================================================
# PAGINAÇÃO
# ==========================================================
def _coletar_paginas_listagem(url_inicial: str, max_paginas: int):

    visitadas = set()
    fila = [url_inicial]
    paginas = []

    while fila and len(paginas) < max_paginas:
        url = fila.pop(0)

        if not url or url in visitadas:
            continue

        visitadas.add(url)

        payload = _fetch(url)
        html = payload.get("html")

        if not html:
            continue

        paginas.append((url, html))

        try:
            novos = extrair_links_paginacao_crawler(html, url)
            for n in novos:
                if n not in visitadas:
                    fila.append(n)
        except Exception:
            pass

    return paginas


# ==========================================================
# 🔥 EXTRAÇÃO FORTE DE LINKS
# ==========================================================
def _extrair_links_agressivo(html: str, base_url: str):

    links = extrair_links_produtos_crawler(html, base_url)

    # 🔥 fallback REAL
    if not links:
        soup = BeautifulSoup(html, "html.parser")

        candidatos = []

        for a in soup.select('a[href*="/produto"]'):
            href = a.get("href")

            if not href:
                continue

            candidatos.append(href.strip())

        links = candidatos

    links = [l for l in links if link_parece_produto_crawler(l)]

    log_debug(f"[LINKS DETECTADOS] {len(links)}")

    return links


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

    progresso = 0

    def tick(valor, msg):
        nonlocal progresso
        progresso = min(100, progresso + valor)
        progress_bar.progress(progresso)
        status.info(msg)

    # ======================================================
    # ETAPA 1
    # ======================================================
    tick(5, "🔎 Iniciando crawler...")

    paginas = _coletar_paginas_listagem(url, max_paginas)

    tick(10, f"📄 {len(paginas)} páginas carregadas")

    # ======================================================
    # ETAPA 2
    # ======================================================
    links = []
    total_paginas = max(len(paginas), 1)

    for i, (p, html) in enumerate(paginas, start=1):
        detalhe.info(f"🔗 Página {i}/{total_paginas}")

        try:
            novos = _extrair_links_agressivo(html, p)
            links.extend(novos)

            status.info(f"🔗 {len(links)} links coletados")

        except Exception:
            pass

        progress_bar.progress(15 + int((i / total_paginas) * 25))

    links = list(dict.fromkeys(links))[:MAX_PRODUTOS]

    # ======================================================
    # FALLBACK FORTE
    # ======================================================
    if not links:
        status.warning("⚠️ Tentando fallback direto...")

        payload = _fetch(url)
        html = payload.get("html")

        if html:
            soup = BeautifulSoup(html, "html.parser")
            links = [
                a.get("href")
                for a in soup.select('a[href*="/produto"]')
                if a.get("href")
            ]

    tick(10, f"🔗 {len(links)} produtos detectados")

    # ======================================================
    # EXTRAÇÃO
    # ======================================================
    if not links:
        status.error("❌ Nenhum produto encontrado")
        return pd.DataFrame()

    tick(5, "📦 Extraindo produtos...")

    resultados = []
    total = len(links)

    with ThreadPoolExecutor(max_workers=max_threads) as ex:
        futs = {ex.submit(_baixar, l, padrao_disponivel): l for l in links}

        for i, f in enumerate(as_completed(futs), start=1):
            r = f.result()

            if r:
                resultados.append(r)

            progresso_extra = int((i / total) * 50)
            progress_bar.progress(50 + progresso_extra)

            detalhe.info(f"⚙️ Produto {i}/{total}")
            status.info(f"📦 Extraindo {i}/{total}")

    # ======================================================
    # FINAL
    # ======================================================
    if not resultados:
        status.error("❌ Nenhum produto válido")
        return pd.DataFrame()

    df = pd.DataFrame(resultados)

    if "Link Externo" in df.columns:
        df = df.drop_duplicates(subset=["Link Externo"])

    progress_bar.progress(100)
    status.success(f"✅ {len(df)} produtos extraídos")

    return df.reset_index(drop=True)
