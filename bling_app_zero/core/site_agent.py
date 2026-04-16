
from __future__ import annotations

import pandas as pd

from bling_app_zero.core.site_crawler_cleaners import normalizar_url, safe_str
from bling_app_zero.core.site_crawler_extractors import extrair_detalhes_heuristicos
from bling_app_zero.core.site_crawler_gpt import gpt_extrair_produto
from bling_app_zero.core.site_crawler_http import fetch_html_retry
from bling_app_zero.core.site_crawler_links import descobrir_produtos_no_dominio
from bling_app_zero.core.site_crawler_validators import produto_final_valido


def _limite_tecnico(limite_links: int | None) -> int:
    limite_padrao = 8000

    if not isinstance(limite_links, int):
        return limite_padrao

    if limite_links <= 0:
        return limite_padrao

    return min(max(limite_links, 1), limite_padrao)


def _montar_linha_saida(final: dict) -> dict:
    return {
        "Código": safe_str(final.get("codigo")),
        "Descrição": safe_str(final.get("descricao")),
        "Categoria": safe_str(final.get("categoria")),
        "GTIN": safe_str(final.get("gtin")),
        "NCM": safe_str(final.get("ncm")),
        "Preço de custo": safe_str(final.get("preco")),
        "Quantidade": safe_str(final.get("quantidade")),
        "URL Imagens": safe_str(final.get("url_imagens")),
        "URL Produto": safe_str(final.get("url_produto")),
    }


def _df_saida(rows: list[dict]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows).fillna("")

    if "URL Produto" in df.columns:
        df = df.drop_duplicates(subset=["URL Produto"], keep="first")

    colunas_ordenadas = [
        "Código",
        "Descrição",
        "Categoria",
        "GTIN",
        "NCM",
        "Preço de custo",
        "Quantidade",
        "URL Imagens",
        "URL Produto",
    ]

    for col in colunas_ordenadas:
        if col not in df.columns:
            df[col] = ""

    return df[colunas_ordenadas].reset_index(drop=True)


def buscar_produtos_site_com_gpt(
    base_url: str,
    termo: str = "",
    limite_links: int | None = None,
) -> pd.DataFrame:
    base_url = normalizar_url(base_url)
    termo = safe_str(termo)

    if not base_url:
        return pd.DataFrame()

    limite = _limite_tecnico(limite_links)

    produtos = descobrir_produtos_no_dominio(
        base_url=base_url,
        termo=termo,
        max_paginas=400,
        max_produtos=limite,
        max_segundos=900,
    )

    if not produtos:
        return pd.DataFrame()

    rows: list[dict] = []
    vistos: set[str] = set()

    for url_produto in produtos:
        url_produto = safe_str(url_produto)
        if not url_produto or url_produto in vistos:
            continue

        try:
            html_produto = fetch_html_retry(url_produto, tentativas=2)
            heuristica = extrair_detalhes_heuristicos(url_produto, html_produto)
            final = gpt_extrair_produto(url_produto, html_produto, heuristica)

            if not produto_final_valido(final):
                continue

            rows.append(_montar_linha_saida(final))
            vistos.add(url_produto)

        except Exception:
            continue

    return _df_saida(rows)
