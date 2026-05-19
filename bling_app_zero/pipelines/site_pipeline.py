from __future__ import annotations

from typing import Callable

import pandas as pd

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.core.text import normalize_key
from bling_app_zero.engines.fast_site_scraper.text_cleaner import clean_product_description
from bling_app_zero.engines.site_operations import run_site_operation_engine


VALID_OPERATIONS = {'cadastro', 'estoque'}
ALL_PAGES_LIMIT = 1_000_000
ALL_PRODUCTS_LIMIT = 1_000_000
DESCRIPTION_COLUMN_SIGNALS = (
    'descricao_complementar',
    'descrição_complementar',
    'descricao_completa',
    'descrição_completa',
    'descricao_detalhada',
    'descrição_detalhada',
    'descricao_do_produto',
    'descrição_do_produto',
    'ficha_tecnica',
    'ficha_técnica',
    'caracteristicas',
    'características',
    'detalhes',
)
TITLE_COLUMN_SIGNALS = (
    'descricao',
    'descrição',
    'nome',
    'produto',
    'titulo',
    'título',
)


def _normalize_operation(operation: str | None) -> str:
    value = str(operation or 'cadastro').strip().lower()
    return value if value in VALID_OPERATIONS else 'cadastro'


def _column_key(column: object) -> str:
    return normalize_key(str(column or '').replace('\n', ' ').replace('\r', ' ')).replace(' ', '_')


def _is_description_column(column: object) -> bool:
    key = _column_key(column)
    if not key:
        return False
    return any(signal in key for signal in DESCRIPTION_COLUMN_SIGNALS)


def _is_title_column(column: object) -> bool:
    key = _column_key(column)
    if not key:
        return False
    return any(signal == key or key.startswith(f'{signal}_') for signal in TITLE_COLUMN_SIGNALS)


def _best_title_column(df: pd.DataFrame) -> str:
    for column in df.columns:
        if _is_title_column(column) and not _is_description_column(column):
            return str(column)
    return ''


def _clean_site_description_columns(df: pd.DataFrame, operation: str) -> pd.DataFrame:
    """Aplica a blindagem de descrição em qualquer motor de site.

    BLINGFIX:
    - o motor genérico já limpava a descrição no extractor;
    - o motor Stoqui/API interna montava o DataFrame direto e podia escapar;
    - esta camada comum roda antes do sanitize/export e impede que avaliações,
      títulos repetidos e seções fora da descrição cheguem ao mapeamento.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df
    if _normalize_operation(operation) != 'cadastro':
        return df

    description_columns = [str(column) for column in df.columns if _is_description_column(column)]
    if not description_columns:
        return df

    out = df.copy().fillna('')
    title_column = _best_title_column(out)
    for column in description_columns:
        if column not in out.columns:
            continue
        for index, value in out[column].items():
            title = str(out.at[index, title_column]) if title_column and title_column in out.columns else ''
            out.at[index, column] = clean_product_description(str(value or ''), title=title, limit=1600)
    return out.fillna('')


def run_pipeline(
    raw_urls: str,
    requested_columns: list[str] | None = None,
    all_products: bool = True,
    max_pages: int = ALL_PAGES_LIMIT,
    max_products: int = ALL_PRODUCTS_LIMIT,
    operation: str = 'cadastro',
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    selected_operation = _normalize_operation(operation)
    selected_max_pages = max(max_pages or 0, ALL_PAGES_LIMIT) if all_products else max_pages
    selected_max_products = max(max_products or 0, ALL_PRODUCTS_LIMIT) if all_products else max_products

    if progress_callback:
        progress_callback({
            'stage': 'Preparando',
            'message': 'Preparando motor separado por operacao...',
            'progress': 0.02,
        })

    df_result = run_site_operation_engine(
        operation=selected_operation,
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        max_pages=selected_max_pages,
        max_products=selected_max_products,
        stop_early=not bool(all_products),
        progress_callback=progress_callback,
    )

    if progress_callback:
        progress_callback({'stage': 'Organizando', 'message': 'Organizando os dados no padrao do Bling...', 'progress': 0.96})
    cleaned_result = _clean_site_description_columns(df_result, selected_operation)
    safe = sanitize_for_bling(cleaned_result, operation=selected_operation)
    if progress_callback:
        progress_callback({'stage': 'Pronto', 'message': f'{len(safe)} produto(s) preparados na origem.', 'progress': 1.0})
    return safe
