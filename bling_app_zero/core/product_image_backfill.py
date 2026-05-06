from __future__ import annotations

"""Backfill de URLs de imagens por página do produto.

Quando a captura/mapeamento vier sem `URL Imagens Externas`, este módulo usa
`Link Externo`/`URL do Produto` para abrir a página real e preencher a imagem.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

import pandas as pd

from bling_app_zero.core.page_by_page_crawler import fetch_html
from bling_app_zero.core.product_image_extractor_safe import extract_safe_product_images


IMAGE_COL = "URL Imagens Externas"
IMAGE_ALIAS_COL = "Imagens"
LINK_COLUMNS = ("Link Externo", "URL do Produto", "url", "URL", "link", "product_url")


def _first_existing_column(df: pd.DataFrame, names: Iterable[str]) -> str:
    if not isinstance(df, pd.DataFrame):
        return ""
    lower_map = {str(c).strip().lower(): str(c) for c in df.columns}
    for name in names:
        found = lower_map.get(str(name).strip().lower())
        if found:
            return found
    return ""


def _has_value(value: object) -> bool:
    return bool(str(value or "").strip() and str(value or "").lower().strip() not in {"nan", "none"})


def _needs_image(row: pd.Series) -> bool:
    if IMAGE_COL not in row.index:
        return True
    return not _has_value(row.get(IMAGE_COL, ""))


def _safe_fetch_images(url: str) -> str:
    try:
        html = fetch_html(url)
        return extract_safe_product_images(url, html)
    except Exception:
        return ""


def backfill_images_by_product_url(df: pd.DataFrame, *, max_workers: int = 10) -> pd.DataFrame:
    """Preenche `URL Imagens Externas` usando o link da página do produto.

    A função não remove nenhum dado existente. Só preenche linhas vazias.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    out = df.copy().fillna("")
    if IMAGE_COL not in out.columns:
        out[IMAGE_COL] = ""
    if IMAGE_ALIAS_COL not in out.columns:
        out[IMAGE_ALIAS_COL] = ""

    link_col = _first_existing_column(out, LINK_COLUMNS)
    if not link_col:
        return out

    pending: dict[int, str] = {}
    for idx, row in out.iterrows():
        if not _needs_image(row):
            continue
        url = str(row.get(link_col, "") or "").strip()
        if url.startswith(("http://", "https://")):
            pending[int(idx)] = url

    if not pending:
        return out

    workers = max(1, min(int(max_workers or 10), 16, len(pending)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_safe_fetch_images, url): idx for idx, url in pending.items()}
        for future in as_completed(futures):
            idx = futures[future]
            try:
                images = future.result()
            except Exception:
                images = ""
            if images:
                out.at[idx, IMAGE_COL] = images
                out.at[idx, IMAGE_ALIAS_COL] = images

    return out.fillna("")
