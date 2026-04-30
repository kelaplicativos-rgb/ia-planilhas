# bling_app_zero/core/instant_scraper/runner.py

from __future__ import annotations

from typing import Any, List

import pandas as pd

from bling_app_zero.core.suppliers.megacenter import MegaCenterSupplier

from .html_fetcher import fetch_html
from .ultra_detector import detectar_blocos_repetidos
from .ultra_extractor import extrair_lista


MAX_CANDIDATOS_RUNNER = 5


def _normalizar_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy().fillna("")

    colunas_base = [
        "fornecedor",
        "url_produto",
        "nome",
        "sku",
        "marca",
        "categoria",
        "preco",
        "estoque",
        "quantidade",
        "quantidade_real",
        "estoque_origem",
        "gtin",
        "descricao",
        "imagens",
        "_diagnostico",
        "_status",
        "_etapa",
        "_motivo",
        "_url_testada",
        "_url_final",
        "_http_status",
        "_html_chars",
        "_links_sitemap",
        "_links_pagina",
        "_links_total",
        "_produtos_extraidos",
    ]

    for col in colunas_base:
        if col not in df.columns:
            df[col] = ""

    for col in df.columns:
        df[col] = df[col].map(lambda x: str(x or "").strip())

    df = df[colunas_base + [c for c in df.columns if c not in colunas_base]]

    if "url_produto" in df.columns:
        df = df.drop_duplicates(subset=["url_produto", "nome"], keep="first")
    else:
        df = df.drop_duplicates(keep="first")

    return df.reset_index(drop=True)


def _diagnostico_df(supplier: MegaCenterSupplier) -> pd.DataFrame:
    diag = getattr(supplier, "last_diagnostics", {}) or {}

    row = {
        "fornecedor": "DIAGNÓSTICO MEGA CENTER",
        "url_produto": diag.get("url_original", ""),
        "nome": "Diagnóstico da busca Mega Center",
        "sku": "",
        "marca": "",
        "categoria": "",
        "preco": "",
        "estoque": "",
        "quantidade": "",
        "quantidade_real": "",
        "estoque_origem": "",
        "gtin": "",
        "descricao": diag.get("resumo", ""),
        "imagens": "",
        "_diagnostico": "SIM",
        "_status": diag.get("status", ""),
        "_etapa": diag.get("etapa", ""),
        "_motivo": diag.get("motivo", ""),
        "_url_testada": diag.get("url_testada", ""),
        "_url_final": diag.get("url_final", ""),
        "_http_status": diag.get("http_status", ""),
        "_html_chars": diag.get("html_chars", ""),
        "_links_sitemap": diag.get("links_sitemap", ""),
        "_links_pagina": diag.get("links_pagina", ""),
        "_links_total": diag.get("links_total", ""),
        "_produtos_extraidos": diag.get("produtos_extraidos", ""),
    }

    return _normalizar_df(pd.DataFrame([row]))


def _run_mega_center(url: str) -> pd.DataFrame:
    supplier = MegaCenterSupplier()

    if not supplier.can_handle(url):
        return pd.DataFrame()

    try:
        produtos = supplier.fetch(
            url,
            limite=300,
            max_paginas=40,
            max_workers=8,
        )
    except Exception as exc:
        supplier.last_diagnostics = {
            "status": "erro",
            "etapa": "runner",
            "motivo": str(exc),
            "url_original": url,
            "resumo": f"Erro no runner Mega Center: {exc}",
        }
        return _diagnostico_df(supplier)

    if produtos:
        try:
            return _normalizar_df(pd.DataFrame(produtos))
        except Exception as exc:
            supplier.last_diagnostics["status"] = "erro"
            supplier.last_diagnostics["etapa"] = "normalizacao_dataframe"
            supplier.last_diagnostics["motivo"] = str(exc)
            supplier.last_diagnostics["resumo"] = f"Erro ao montar DataFrame: {exc}"
            return _diagnostico_df(supplier)

    return _diagnostico_df(supplier)


def _run_generico(url: str) -> pd.DataFrame:
    try:
        html = fetch_html(url)
    except Exception:
        return pd.DataFrame()

    if not html:
        return pd.DataFrame()

    try:
        candidates: List[dict[str, Any]] = detectar_blocos_repetidos(html)
    except Exception:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []

    for candidate in candidates[:MAX_CANDIDATOS_RUNNER]:
        try:
            elements = candidate.get("elements", [])[:80]
            produtos = extrair_lista(elements, url)

            if produtos:
                frames.append(pd.DataFrame(produtos))
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()

    try:
        df = pd.concat(frames, ignore_index=True)
    except Exception:
        return pd.DataFrame()

    return _normalizar_df(df)


def run_scraper(url: str) -> pd.DataFrame:
    url = str(url or "").strip()
    if not url:
        return pd.DataFrame()

    supplier = MegaCenterSupplier()
    if supplier.can_handle(url):
        return _run_mega_center(url)

    return _run_generico(url)
