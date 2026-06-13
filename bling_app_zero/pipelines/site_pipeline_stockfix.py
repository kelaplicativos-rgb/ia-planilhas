from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import pandas as pd
import requests

from bling_app_zero.core.audit import add_audit_event
from bling_app_zero.core.text import clean_cell
from bling_app_zero.engines.real_stock_detector import detect_real_stock_detail
from bling_app_zero.pipelines.site_pipeline_blingfix import run_pipeline as _base_run_pipeline

RESPONSIBLE_FILE = 'bling_app_zero/pipelines/site_pipeline_stockfix.py'
PAGE_TIMEOUT = 14
MAX_WORKERS = 8
STOCK_ALIASES = ('estoque', 'quantidade', 'qtd', 'saldo', 'balanco', 'balanço', 'inventory', 'stock')
URL_ALIASES = ('url', 'link', 'produto url', 'url produto', 'origem url', 'link produto')


def _key(value: object) -> str:
    text = str(value or '').strip().lower()
    text = text.replace('ã', 'a').replace('á', 'a').replace('à', 'a').replace('â', 'a')
    text = text.replace('é', 'e').replace('ê', 'e').replace('í', 'i')
    text = text.replace('ó', 'o').replace('ô', 'o').replace('õ', 'o').replace('ú', 'u').replace('ç', 'c')
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', text)).strip()


def _find_col(df: pd.DataFrame, aliases: tuple[str, ...]) -> str:
    alias_keys = {_key(alias) for alias in aliases}
    for column in df.columns:
        col_key = _key(column)
        if col_key in alias_keys:
            return str(column)
    for column in df.columns:
        col_key = _key(column)
        if any(alias in col_key for alias in alias_keys):
            return str(column)
    return ''


def _stock_requested(requested_columns: list[str] | None, operation: str) -> bool:
    if _key(operation) == 'estoque':
        return True
    return any(_key(column) in {_key(alias) for alias in STOCK_ALIASES} for column in (requested_columns or []))


def _fetch_stock(url: str) -> tuple[str, str, str]:
    clean_url = clean_cell(url)
    if not clean_url.startswith(('http://', 'https://')):
        return '', '', ''
    try:
        response = requests.get(
            clean_url,
            timeout=PAGE_TIMEOUT,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'pt-BR,pt;q=0.9,en;q=0.8',
            },
        )
        if response.status_code >= 400:
            return '', '', f'http/{response.status_code}'
        html = response.text or ''
        detail = detect_real_stock_detail(url=clean_url, html=html, text='')
        quantity = clean_cell(detail.quantity)
        if not quantity and str(detail.source or '').endswith('status/in'):
            # Sites que ocultam o saldo real, mas confirmam disponibilidade,
            # recebem o saldo operacional conservador usado pelo fluxo Bling.
            quantity = '10'
            return quantity, 'baixa', 'status/in-fallback'
        return quantity, str(detail.confidence or ''), str(detail.source or '')
    except Exception as exc:
        return '', '', f'erro/{type(exc).__name__}'


def enrich_site_stock(
    df: pd.DataFrame,
    *,
    requested_columns: list[str] | None,
    operation: str,
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty or not _stock_requested(requested_columns, operation):
        return df

    out = df.copy().fillna('')
    url_col = _find_col(out, URL_ALIASES)
    if not url_col:
        add_audit_event(
            'site_stockfix_without_url',
            area='SITE',
            status='BLOQUEADO',
            details={'reason': 'Modelo pediu estoque, mas a busca não devolveu URL do produto.', 'responsible_file': RESPONSIBLE_FILE},
        )
        return out

    stock_col = _find_col(out, STOCK_ALIASES)
    if not stock_col:
        stock_col = 'Estoque'
        out[stock_col] = ''

    pending_by_url: dict[str, list[object]] = {}
    for index, row in out.iterrows():
        if clean_cell(row.get(stock_col, '')):
            continue
        url = clean_cell(row.get(url_col, ''))
        if url:
            pending_by_url.setdefault(url, []).append(index)

    total = len(pending_by_url)
    captured = 0
    fallback = 0
    zero = 0
    unresolved = 0
    sources: dict[str, int] = {}

    if progress_callback and total:
        progress_callback({'stage': 'Lendo estoque', 'message': f'Consultando estoque de {total} produto(s) no site.', 'progress': 0.94})

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(_fetch_stock, url): url for url in pending_by_url}
        completed = 0
        for future in as_completed(futures):
            url = futures[future]
            quantity, confidence, source = future.result()
            completed += 1
            source = source or 'nao_detectado'
            sources[source] = sources.get(source, 0) + 1
            if quantity != '':
                for index in pending_by_url[url]:
                    out.at[index, stock_col] = quantity
                captured += len(pending_by_url[url])
                if quantity == '0':
                    zero += len(pending_by_url[url])
                if source == 'status/in-fallback':
                    fallback += len(pending_by_url[url])
            else:
                unresolved += len(pending_by_url[url])
            if progress_callback and (completed % 10 == 0 or completed == total):
                progress_callback({
                    'stage': 'Lendo estoque',
                    'message': f'Estoque verificado em {completed} de {total} produto(s).',
                    'progress': min(0.985, 0.94 + (0.045 * completed / max(total, 1))),
                })

    add_audit_event(
        'site_stockfix_completed',
        area='SITE',
        status='OK' if captured else 'AVISO',
        details={
            'rows': len(out),
            'urls_checked': total,
            'captured_rows': captured,
            'zero_rows': zero,
            'availability_fallback_rows': fallback,
            'unresolved_rows': unresolved,
            'stock_column': stock_col,
            'url_column': url_col,
            'sources': sources,
            'operation': operation,
            'responsible_file': RESPONSIBLE_FILE,
        },
    )
    return out.fillna('')


def run_pipeline(
    raw_urls: str,
    requested_columns: list[str] | None = None,
    all_products: bool = True,
    max_pages: int = 0,
    max_products: int = 0,
    operation: str = 'universal',
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    df = _base_run_pipeline(
        raw_urls,
        requested_columns=requested_columns,
        all_products=all_products,
        max_pages=max_pages,
        max_products=max_products,
        operation=operation,
        progress_callback=progress_callback,
    )
    return enrich_site_stock(
        df,
        requested_columns=requested_columns,
        operation=str(operation or ''),
        progress_callback=progress_callback,
    )


__all__ = ['enrich_site_stock', 'run_pipeline']
