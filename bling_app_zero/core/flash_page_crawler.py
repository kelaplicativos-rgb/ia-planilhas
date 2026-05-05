from __future__ import annotations

"""Flash Amplo página por página em velocidade máxima.

Estratégia oficial:
1. Descobrir links `/produto/...` primeiro pela varredura normal/listagens.
2. Usar sitemap por último, apenas para complementar URLs ainda não detectadas.
3. Entrar em cada página de produto em paralelo.
4. Extrair dados reais da página individual.
5. Marca é tratada no normalizador apenas pelo título do produto.
6. Não tornar estoque obrigatório.

Este módulo é o motor rápido do fluxo. Mesmo se uma tela antiga chamar o crawler
sem informar limite, o padrão interno fica alto para não cortar produtos cedo.
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
DEFAULT_MAX_PRODUCTS = 5000
MAX_WORKERS_HARD_LIMIT = 32


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
    effective_max_products = int(max_products or DEFAULT_MAX_PRODUCTS)
    product_urls = discover_product_urls(seed_urls, max_products=effective_max_products, use_sitemap=True)
    total = len(product_urls)

    if total == 0:
        return []

    workers = max(1, min(int(max_workers or DEFAULT_MAX_WORKERS), MAX_WORKERS_HARD_LIMIT, total))
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
