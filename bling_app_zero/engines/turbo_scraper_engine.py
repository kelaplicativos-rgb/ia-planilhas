from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Iterable

import pandas as pd

from bling_app_zero.core.text import normalize_key
from bling_app_zero.engines.flash_amplo_engine import run_flash_amplo_page_mode, scrape_urls, split_urls
from bling_app_zero.engines.instant_scraper_engine import run_instant_scraper
from bling_app_zero.engines.power_scraper_engine import run_power_scraper

MAX_TURBO_WORKERS = 3


@dataclass(frozen=True)
class TurboSource:
    name: str
    runner: Callable[[], pd.DataFrame]


def _clean_columns(columns: Iterable[str] | None) -> list[str] | None:
    result = [str(column).strip() for column in (columns or []) if str(column).strip()]
    return result or None


def _has_real_rows(df: pd.DataFrame | None) -> bool:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return False
    for _, row in df.iterrows():
        if any(str(value or '').strip() for value in row.to_dict().values()):
            return True
    return False


def _row_score(row: dict[str, object]) -> int:
    score = 0
    for key, value in row.items():
        text = str(value or '').strip()
        if not text:
            continue
        score += 1
        key_norm = normalize_key(key)
        if any(term in key_norm for term in ['descricao', 'nome', 'produto']):
            score += 4
        elif any(term in key_norm for term in ['preco', 'valor']):
            score += 3
        elif any(term in key_norm for term in ['estoque', 'balanco', 'quantidade', 'saldo']):
            score += 3
        elif any(term in key_norm for term in ['imagem', 'foto']):
            score += 3
        elif any(term in key_norm for term in ['codigo', 'sku', 'referencia', 'gtin', 'ean']):
            score += 2
    return score


def _row_identity(row: dict[str, object]) -> str:
    normalized_items = {normalize_key(key): str(value or '').strip() for key, value in row.items()}
    for key in ['url', 'link', 'codigo', 'sku', 'referencia', 'gtin', 'ean']:
        value = normalized_items.get(key, '')
        if value:
            return f'{key}:{normalize_key(value)}'
    for key, value in normalized_items.items():
        if any(term in key for term in ['descricao', 'nome', 'produto']) and value:
            return f'nome:{normalize_key(value)[:90]}'
    joined = '|'.join(f'{key}:{value}' for key, value in sorted(normalized_items.items()) if value)
    return normalize_key(joined)[:120]


def _merge_rows(base: dict[str, object], incoming: dict[str, object]) -> dict[str, object]:
    out = dict(base)
    for key, value in incoming.items():
        current = str(out.get(key, '') or '').strip()
        candidate = str(value or '').strip()
        key_norm = normalize_key(key)
        if not current and candidate:
            out[key] = candidate
            continue
        if candidate and len(candidate) > len(current) and any(term in key_norm for term in ['descricao', 'imagem', 'foto', 'categoria']):
            out[key] = candidate
    return out


def _merge_dataframes(frames: list[pd.DataFrame], requested_columns: list[str] | None, keep_only_requested_columns: bool) -> pd.DataFrame:
    valid = [df.copy().fillna('') for df in frames if _has_real_rows(df)]
    if not valid:
        return pd.DataFrame(columns=requested_columns or [])

    rows_by_id: dict[str, dict[str, object]] = {}
    for df in valid:
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            if not any(str(value or '').strip() for value in row_dict.values()):
                continue
            identity = _row_identity(row_dict)
            if not identity:
                identity = f'row:{len(rows_by_id)}'
            if identity not in rows_by_id:
                rows_by_id[identity] = row_dict
            else:
                rows_by_id[identity] = _merge_rows(rows_by_id[identity], row_dict)

    rows = sorted(rows_by_id.values(), key=_row_score, reverse=True)
    out = pd.DataFrame(rows).fillna('')

    if requested_columns and keep_only_requested_columns:
        for column in requested_columns:
            if column not in out.columns:
                out[column] = ''
        return out.loc[:, requested_columns].fillna('')

    return out.fillna('')


def _flash_dataframe(
    raw_urls: str,
    columns: list[str] | None,
    all_products: bool,
    max_pages: int,
    max_products: int,
    keep_only_requested_columns: bool,
) -> pd.DataFrame:
    urls = split_urls(raw_urls)
    if not urls:
        return pd.DataFrame(columns=columns or [])
    if all_products:
        return run_flash_amplo_page_mode(
            raw_urls=raw_urls,
            requested_columns=columns,
            max_pages=max_pages,
            max_products=max_products,
            keep_only_requested_columns=keep_only_requested_columns,
        ).fillna('')
    return scrape_urls(urls, requested_columns=columns).fillna('')


def run_turbo_scraper(
    raw_urls: str,
    requested_columns: Iterable[str] | None = None,
    operation: str = 'cadastro',
    all_products: bool = True,
    max_pages: int = 250,
    max_products: int = 1000,
    keep_only_requested_columns: bool = True,
) -> pd.DataFrame:
    """Orquestra diversas fontes em paralelo e consolida o melhor resultado.

    Fontes usadas:
    - Power Scraper: sitemaps, robots, feeds, cards, JSON-LD e IA complementar.
    - Instant Scraper: detecção de cards/listagens estilo extensão.
    - Flash Amplo: motor legado como terceira fonte.
    """
    columns = _clean_columns(requested_columns)
    if not split_urls(raw_urls):
        return pd.DataFrame(columns=columns or [])

    sources = [
        TurboSource(
            name='power',
            runner=lambda: run_power_scraper(
                raw_urls=raw_urls,
                requested_columns=columns,
                operation=operation,
                all_products=all_products,
                max_pages=max_pages,
                max_products=max_products,
                keep_only_requested_columns=keep_only_requested_columns,
            ),
        ),
        TurboSource(
            name='instant',
            runner=lambda: run_instant_scraper(
                raw_urls=raw_urls,
                requested_columns=columns,
                operation=operation,
                all_products=all_products,
                max_pages=max_pages,
                max_products=max_products,
                keep_only_requested_columns=keep_only_requested_columns,
            ),
        ),
        TurboSource(
            name='flash',
            runner=lambda: _flash_dataframe(
                raw_urls=raw_urls,
                columns=columns,
                all_products=all_products,
                max_pages=max_pages,
                max_products=max_products,
                keep_only_requested_columns=keep_only_requested_columns,
            ),
        ),
    ]

    frames: list[pd.DataFrame] = []
    with ThreadPoolExecutor(max_workers=MAX_TURBO_WORKERS) as executor:
        futures = {executor.submit(source.runner): source.name for source in sources}
        for future in as_completed(futures):
            try:
                df = future.result()
                if _has_real_rows(df):
                    frames.append(df)
            except Exception:
                continue

    result = _merge_dataframes(frames, columns, keep_only_requested_columns)
    if max_products > 0 and len(result) > max_products:
        result = result.head(max_products)
    return result.fillna('')
