from __future__ import annotations

"""Flash Amplo página por página em velocidade máxima com checkpoint.

Estratégia oficial:
1. Descobrir links `/produto/...` primeiro pela varredura normal/listagens.
2. Usar sitemap por último, apenas para complementar URLs ainda não detectadas.
3. Entrar em cada página de produto em paralelo.
4. Salvar cada produto capturado em checkpoint local.
5. Se a sessão reiniciar, reaproveitar produtos já capturados da mesma busca.
6. Extrair dados reais da página individual.
7. Marca é tratada no normalizador apenas pelo título do produto.
8. Não tornar estoque obrigatório.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, Optional

import pandas as pd

from bling_app_zero.core.flash_checkpoint import (
    append_checkpoint_row,
    fingerprint_urls,
    load_checkpoint_rows,
)
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


def _row_url(row: dict[str, object]) -> str:
    return str(row.get("Link Externo") or row.get("URL do Produto") or "").strip()


def crawl_flash_amplo_page_by_page(
    seed_urls: Iterable[str],
    *,
    max_products: int = DEFAULT_MAX_PRODUCTS,
    max_workers: int = DEFAULT_MAX_WORKERS,
    progress_callback: ProgressCallback = None,
    use_checkpoint: bool = True,
) -> list[dict[str, str]]:
    """Executa captura Flash Amplo entrando em cada página de produto."""
    seed_list = [str(url or "").strip() for url in seed_urls if str(url or "").strip()]
    effective_max_products = int(max_products or DEFAULT_MAX_PRODUCTS)
    product_urls = discover_product_urls(seed_list, max_products=effective_max_products, use_sitemap=True)
    total = len(product_urls)

    if total == 0:
        return []

    fingerprint = fingerprint_urls(seed_list, max_products=effective_max_products)
    checkpoint_rows = load_checkpoint_rows(fingerprint) if use_checkpoint else []
    rows_by_url: dict[str, dict[str, str]] = {}
    for row in checkpoint_rows:
        url = _row_url(row)
        if url:
            rows_by_url[url] = row

    pending_urls = [url for url in product_urls if url not in rows_by_url]
    done_initial = total - len(pending_urls)

    if progress_callback and done_initial > 0:
        progress_callback(done_initial, total, "checkpoint")

    if not pending_urls:
        return [rows_by_url[url] for url in product_urls if url in rows_by_url]

    workers = max(1, min(int(max_workers or DEFAULT_MAX_WORKERS), MAX_WORKERS_HARD_LIMIT, len(pending_urls)))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_safe_extract_one, url): url for url in pending_urls}
        for offset, future in enumerate(as_completed(futures), start=1):
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
            row_url = _row_url(row) or url
            rows_by_url[row_url] = row
            if use_checkpoint:
                append_checkpoint_row(fingerprint, row)
            if progress_callback:
                progress_callback(done_initial + offset, total, url)

    return [rows_by_url[url] for url in product_urls if url in rows_by_url]


def crawl_flash_amplo_page_by_page_dataframe(
    seed_urls: Iterable[str],
    *,
    max_products: int = DEFAULT_MAX_PRODUCTS,
    max_workers: int = DEFAULT_MAX_WORKERS,
    progress_callback: ProgressCallback = None,
    use_checkpoint: bool = True,
) -> pd.DataFrame:
    rows = crawl_flash_amplo_page_by_page(
        seed_urls,
        max_products=max_products,
        max_workers=max_workers,
        progress_callback=progress_callback,
        use_checkpoint=use_checkpoint,
    )
    return pd.DataFrame(rows)
