from __future__ import annotations

"""Flash Amplo página por página em velocidade máxima com checkpoint.

Regra atual:
- descoberta de produtos por página infinity controlada;
- não para na primeira página;
- abre cada `/produto/...`;
- imagens passam pelo extrator seguro, sem aceitar URL de produto como imagem.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Iterable, Optional

import pandas as pd

from bling_app_zero.core.flash_checkpoint import append_checkpoint_row, fingerprint_urls, load_checkpoint_rows
from bling_app_zero.core.page_by_page_crawler import extract_product_from_page, fetch_html
from bling_app_zero.core.product_image_extractor_safe import extract_safe_product_images
from bling_app_zero.core.product_url_discovery_infinity import discover_product_urls_infinity


ProgressCallback = Optional[Callable[[int, int, str], None]]

DEFAULT_MAX_WORKERS = 12
DEFAULT_MAX_PRODUCTS = 5000
MAX_WORKERS_HARD_LIMIT = 32


def _safe_extract_one(product_url: str) -> dict[str, str]:
    try:
        html = fetch_html(product_url)
        row = extract_product_from_page(product_url, html)

        imagens = extract_safe_product_images(product_url, html)
        if imagens:
            row["URL Imagens Externas"] = imagens
            row["Imagens"] = imagens

        row.setdefault("Link Externo", product_url)
        row.setdefault("URL do Produto", product_url)
        row.setdefault("Fonte captura", "flash_amplo_pagina_produto")
        row["_url_descoberta_flash"] = product_url
        return row
    except Exception as exc:  # noqa: BLE001
        return {
            "Link Externo": product_url,
            "URL do Produto": product_url,
            "Fonte captura": "flash_amplo_pagina_produto_erro",
            "Erro captura": str(exc),
            "_url_descoberta_flash": product_url,
        }


def _row_url(row: dict[str, object]) -> str:
    return str(row.get("_url_descoberta_flash") or row.get("Link Externo") or row.get("URL do Produto") or "").strip()


def _clean_internal_keys(row: dict[str, str]) -> dict[str, str]:
    cleaned = dict(row)
    cleaned.pop("_url_descoberta_flash", None)
    return cleaned


def crawl_flash_amplo_page_by_page(
    seed_urls: Iterable[str],
    *,
    max_products: int = DEFAULT_MAX_PRODUCTS,
    max_workers: int = DEFAULT_MAX_WORKERS,
    progress_callback: ProgressCallback = None,
    use_checkpoint: bool = True,
) -> list[dict[str, str]]:
    seed_list = [str(url or "").strip() for url in seed_urls if str(url or "").strip()]
    effective_max_products = int(max_products or DEFAULT_MAX_PRODUCTS)

    product_urls = discover_product_urls_infinity(seed_list, max_products=effective_max_products)
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

    if pending_urls:
        workers = max(1, min(int(max_workers or DEFAULT_MAX_WORKERS), MAX_WORKERS_HARD_LIMIT, len(pending_urls)))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_safe_extract_one, url): url for url in pending_urls}
            for offset, future in enumerate(as_completed(futures), start=1):
                discovered_url = futures[future]
                try:
                    row = future.result()
                except Exception as exc:  # noqa: BLE001
                    row = {
                        "Link Externo": discovered_url,
                        "URL do Produto": discovered_url,
                        "Fonte captura": "flash_amplo_pagina_produto_erro",
                        "Erro captura": str(exc),
                        "_url_descoberta_flash": discovered_url,
                    }
                rows_by_url[discovered_url] = row
                canonical = str(row.get("Link Externo") or row.get("URL do Produto") or "").strip()
                if canonical:
                    rows_by_url.setdefault(canonical, row)
                if use_checkpoint:
                    append_checkpoint_row(fingerprint, row)
                if progress_callback:
                    progress_callback(done_initial + offset, total, discovered_url)

    ordered_rows = []
    for url in product_urls:
        row = rows_by_url.get(url)
        if row:
            ordered_rows.append(_clean_internal_keys(row))
    return ordered_rows


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
