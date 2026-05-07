from __future__ import annotations

"""Backfill de URLs de imagens por página do produto."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Iterable

import pandas as pd

from bling_app_zero.core.page_by_page_crawler import fetch_html
from bling_app_zero.core.product_image_extractor_safe import extract_safe_product_images


IMAGE_COL = "URL Imagens Externas"
IMAGE_ALIAS_COL = "Imagens"
LINK_COLUMNS = ("Link Externo", "URL do Produto", "url", "URL", "link", "product_url")
TITLE_COLUMNS = ("Descrição", "Descricao", "Descrição Produto", "Descricao Produto", "Nome", "Produto", "Título", "Titulo", "Title", "name")


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


def _safe_fetch_images(url: str, product_title: str = "", validate_remote: bool = False) -> str:
    try:
        html = fetch_html(url)
        return extract_safe_product_images(url, html, product_title=product_title, validate_remote=validate_remote)
    except Exception:
        return ""


def backfill_images_by_product_url(
    df: pd.DataFrame,
    *,
    max_workers: int = 10,
    validate_remote: bool = False,
) -> pd.DataFrame:
    """Preenche `URL Imagens Externas` usando o link da página do produto."""
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    out = df.copy().fillna("")
    if IMAGE_COL not in out.columns:
        out[IMAGE_COL] = ""
    if IMAGE_ALIAS_COL not in out.columns:
        out[IMAGE_ALIAS_COL] = ""

    link_col = _first_existing_column(out, LINK_COLUMNS)
    title_col = _first_existing_column(out, TITLE_COLUMNS)
    if not link_col:
        return out

    pending: dict[int, tuple[str, str]] = {}
    for idx, row in out.iterrows():
        if not _needs_image(row):
            continue
        url = str(row.get(link_col, "") or "").strip()
        if url.startswith(("http://", "https://")):
            title = str(row.get(title_col, "") or "").strip() if title_col else ""
            pending[int(idx)] = (url, title)

    if not pending:
        return out

    workers = max(1, min(int(max_workers or 10), 12, len(pending)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_safe_fetch_images, url, title, validate_remote): idx
            for idx, (url, title) in pending.items()
        }
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
