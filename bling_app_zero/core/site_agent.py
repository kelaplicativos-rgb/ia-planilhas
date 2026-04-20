
# 🔥 BLINGMASTERFIX - SITE AGENT ROBUSTO

from __future__ import annotations

import re
from typing import Any

import pandas as pd

# 🔥 IMPORTS BLINDADOS
try:
    from bling_app_zero.core.site_crawler_cleaners import normalizar_url, safe_str
except:
    normalizar_url = lambda x: x
    safe_str = lambda x: str(x or "")

try:
    from bling_app_zero.core.site_crawler_extractors import extrair_detalhes_heuristicos
except:
    extrair_detalhes_heuristicos = None

try:
    from bling_app_zero.core.site_crawler_gpt import gpt_extrair_produto
except:
    gpt_extrair_produto = None

try:
    from bling_app_zero.core.site_crawler_http import fetch_html_retry
except:
    fetch_html_retry = None

try:
    from bling_app_zero.core.site_crawler_links import descobrir_produtos_no_dominio
except:
    descobrir_produtos_no_dominio = None

try:
    from bling_app_zero.core.site_crawler_validators import (
        pontuar_produto,
        produto_final_valido,
        titulo_valido,
    )
except:
    pontuar_produto = lambda **k: 0
    produto_final_valido = lambda x: True
    titulo_valido = lambda *a, **k: True


def _resolver_final(heuristica: dict, final: dict) -> dict:
    """🔥 fallback inteligente GPT + heurística"""

    base = {}

    for campo in [
        "descricao",
        "categoria",
        "marca",
        "url_imagens",
        "codigo",
        "gtin",
        "ncm",
        "preco",
    ]:
        base[campo] = (
            safe_str(final.get(campo))
            or safe_str(heuristica.get(campo))
        )

    base["url_produto"] = safe_str(final.get("url_produto"))
    return base


def buscar_produtos_site_com_gpt(
    base_url: str,
    termo: str = "",
    limite_links: int | None = None,
    diagnostico: bool = False,
) -> pd.DataFrame:

    base_url = normalizar_url(base_url)

    if not base_url or not descobrir_produtos_no_dominio:
        return pd.DataFrame()

    produtos = descobrir_produtos_no_dominio(
        base_url=base_url,
        termo=termo,
        max_paginas=100,
        max_produtos=1000,
        max_segundos=300,
    )

    if not produtos:
        return pd.DataFrame()

    rows = []
    vistos = set()

    for url in produtos:

        if not url or url in vistos:
            continue

        # 🔥 FETCH HTML
        try:
            html = fetch_html_retry(url, tentativas=2) if fetch_html_retry else ""
        except:
            continue

        # 🔥 HEURÍSTICA
        heuristica = {}
        if extrair_detalhes_heuristicos:
            try:
                heuristica = extrair_detalhes_heuristicos(url, html)
            except:
                heuristica = {}

        # 🔥 GPT COM RETRY
        final = {}
        if gpt_extrair_produto:
            for _ in range(2):
                try:
                    final = gpt_extrair_produto(url, html, heuristica)
                    if final:
                        break
                except:
                    final = {}

        # 🔥 FALLBACK FINAL
        final = _resolver_final(heuristica, final)

        if not final.get("descricao"):
            continue

        rows.append({
            "Código": final.get("codigo"),
            "Descrição": final.get("descricao"),
            "Categoria": final.get("categoria"),
            "Marca": final.get("marca"),
            "GTIN": final.get("gtin"),
            "NCM": final.get("ncm"),
            "Preço de custo": final.get("preco"),
            "Quantidade": "1",
            "URL Imagens": final.get("url_imagens"),
            "URL Produto": final.get("url_produto"),
        })

        vistos.add(url)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).fillna("")
    df = df.drop_duplicates(subset=["URL Produto"], keep="first")

    return df.reset_index(drop=True)
