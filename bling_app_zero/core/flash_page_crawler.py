from __future__ import annotations

"""Flash Amplo página por página em velocidade máxima.

Estratégia:
1. Descobrir links `/produto/...` rapidamente em listagens/categorias.
2. Entrar em cada página de produto em paralelo.
3. Extrair dados obrigatórios da página real do produto.
4. Não tornar estoque obrigatório.

Este módulo complementa `page_by_page_crawler.py` com execução concorrente para
manter o modo Flash Amplo rápido sem voltar a depender de cards/listagens.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, Optional

import pandas as pd

from bling_app_zero.core.page_by_page_crawler import (
    discover_product_urls,
    extract_product_from_page,
    fetch_html,
)


ProgressCallback = Optional[Callable[[int, int, str], None]]


DEFAULT_MAX_WORKERS = 12
DEFAULT_MAX_PRODUCTS = 500


def _safe_extract_one(product_url: str) -> dict[str, str]:
    try:
        html = fetch_html(product_url)
        row = extract_product_from_page(product_url, html)
        row.setdefault("Link Externo", product_url)
        row.setdefault("URL do Produto", product_url)
        row.setdefault("Fonte captura", "flash_amplo_pagina_produto")
        return row
    except Exception as exc:  # noqa: BLE001
        return {
            "Link Externo": product_url,
            "URL do Produto": product_url,
            "Fonte captura": "flash_amplo_pagina_produto_erro",
            "Erro captura": str(exc),
        }


def crawl_flash_amplo_page_by_page(
    seed_urls: Iterable[str],
    *,
    max_products: int = DEFAULT_MAX_PRODUCTS,
    max_workers: int = DEFAULT_MAX_WORKERS,
    progress_callback: ProgressCallback = None,
) -> list[dict[str, str]]:
    """Executa captura Flash Amplo entrando em cada página de produto."""
    product_urls = discover_product_urls(seed_urls, max_products=max_products)
    total = len(product_urls)

    if total == 0:
        return []

    workers = max(1, min(int(max_workers or DEFAULT_MAX_WORKERS), 32, total))
    rows: list[dict[str, str]] = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_safe_extract_one, url): url for url in product_urls}
        for done_count, future in enumerate(as_completed(futures), start=1):
            url = futures[future]
            try:
                row = future.result()
            except Exception as exc:  # noqa: BLE001
                row = {
                    "Link Externo": url,
                    "URL do Produto": url,
                    "Fonte captura": "flash_amplo_pagina_produto_erro",
                    "Erro captura": str(exc),
                }
            rows.append(row)
            if progress_callback:
                progress_callback(done_count, total, url)

    # Mantém ordem previsível conforme descoberta, mesmo executando em paralelo.
    by_url = {str(row.get("Link Externo") or row.get("URL do Produto") or ""): row for row in rows}
    ordered_rows = [by_url.get(url) for url in product_urls if by_url.get(url)]
    return ordered_rows


def crawl_flash_amplo_page_by_page_dataframe(
    seed_urls: Iterable[str],
    *,
    max_products: int = DEFAULT_MAX_PRODUCTS,
    max_workers: int = DEFAULT_MAX_WORKERS,
    progress_callback: ProgressCallback = None,
) -> pd.DataFrame:
    rows = crawl_flash_amplo_page_by_page(
        seed_urls,
        max_products=max_products,
        max_workers=max_workers,
        progress_callback=progress_callback,
    )
    return pd.DataFrame(rows)
