from __future__ import annotations

import re
from typing import Callable

import pandas as pd

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.core.text import clean_cell, normalize_key
from bling_app_zero.engines.fast_site_scraper.constants import (
    SAFE_CAPTURE_MAX_PAGES,
    SAFE_CAPTURE_MAX_PRODUCTS,
    normalize_capture_limits,
)
from bling_app_zero.engines.fast_site_scraper.text_cleaner import clean_product_description
from bling_app_zero.engines.site_operations import run_site_operation_engine
from bling_app_zero.universal.model_contract_detector import normalize_contract_operation


VALID_OPERATIONS = {'cadastro', 'estoque', 'universal', 'atualizacao_preco'}
UNIVERSAL_ALIASES = {'universal', 'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}
ALL_PAGES_LIMIT = SAFE_CAPTURE_MAX_PAGES
ALL_PRODUCTS_LIMIT = SAFE_CAPTURE_MAX_PRODUCTS
ESTOQUE_COLUMN_SIGNALS = (
    'estoque',
    'saldo',
    'quantidade',
    'balanco',
    'balanço',
    'deposito',
    'depósito',
)
PRICE_UPDATE_COLUMN_SIGNALS = (
    'preco',
    'preço',
    'preco_unitario',
    'preço_unitário',
    'preco unitario',
    'preço unitário',
    'valor',
    'valor_unitario',
    'valor unitario',
    'custo',
)
ID_COLUMN_SIGNALS = (
    'id',
    'id_produto',
    'id produto',
    'codigo',
    'código',
    'sku',
    'gtin',
    'ean',
)
CADASTRO_ONLY_COLUMN_SIGNALS = (
    'imagem',
    'imagens',
    'url_imagens',
    'marca',
    'categoria',
    'ncm',
    'descricao_complementar',
    'descrição_complementar',
    'caracteristicas',
    'características',
    'ficha_tecnica',
    'ficha_técnica',
)
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
PLAIN_DESCRIPTION_COLUMN_SIGNALS = (
    'descricao',
    'descrição',
)
TITLE_COLUMN_SIGNALS = (
    'nome',
    'produto',
    'titulo',
    'título',
)
FALLBACK_TITLE_COLUMN_SIGNALS = (
    'descricao',
    'descrição',
)
DESCRIPTION_NOISE_SIGNALS = (
    'ainda nao ha para este produto',
    'ainda não há para este produto',
    'ainda nao ha avaliacoes para este produto',
    'ainda não há avaliações para este produto',
    'avaliacoes',
    'avaliações',
    'seja o primeiro a avaliar',
    'entre para avaliar',
    'calcule o frete',
    'compartilhar produto',
    'continuar comprando',
    'adicionar',
    'comprar',
    'veja como pagar',
)
LONG_DESCRIPTION_MIN_CHARS = 90
LONG_DESCRIPTION_MIN_WORDS = 14


def _normalize_operation(operation: str | None) -> str:
    normalized = normalize_contract_operation(operation)
    if normalized in VALID_OPERATIONS:
        return normalized
    value = str(operation or 'universal').strip().lower()
    if value in {'estoque', 'stock', 'atualizacao_estoque', 'atualização de estoque', 'estoque_site'}:
        return 'estoque'
    if value in {'cadastro', 'cadastro_site', 'produtos', 'produto'}:
        return 'cadastro'
    if value in UNIVERSAL_ALIASES:
        return 'universal'
    return 'universal'


def _safe_positive_int(value: int | None, fallback: int) -> int:
    try:
        parsed = int(value or 0)
    except Exception:
        parsed = 0
    return parsed if parsed > 0 else fallback


def _bounded_limit(value: int | None, fallback: int, hard_limit: int) -> int:
    return min(_safe_positive_int(value, fallback), hard_limit)


def _column_key(column: object) -> str:
    return normalize_key(str(column or '').replace('\n', ' ').replace('\r', ' ')).replace(' ', '_')


def _has_any_signal(key: str, signals: tuple[str, ...]) -> bool:
    return any(normalize_key(signal).replace(' ', '_') in key for signal in signals)


def _infer_operation_from_columns(operation: str, requested_columns: list[str] | None) -> str:
    """Preserva o fluxo universal, mas escolhe o motor correto pelo modelo anexado."""
    normalized = _normalize_operation(operation)
    if normalized != 'universal':
        return normalized

    keys = [_column_key(column) for column in (requested_columns or [])]
    has_estoque_signal = any(_has_any_signal(key, ESTOQUE_COLUMN_SIGNALS) for key in keys)
    has_cadastro_only_signal = any(_has_any_signal(key, CADASTRO_ONLY_COLUMN_SIGNALS) for key in keys)
    has_price_signal = any(_has_any_signal(key, PRICE_UPDATE_COLUMN_SIGNALS) for key in keys)
    has_id_signal = any(_has_any_signal(key, ID_COLUMN_SIGNALS) for key in keys)

    if has_estoque_signal and not has_cadastro_only_signal:
        return 'estoque'
    if has_price_signal and has_id_signal and not has_estoque_signal and not has_cadastro_only_signal:
        return 'atualizacao_preco'
    return normalized


def _value_key(value: object) -> str:
    return normalize_key(clean_cell(value))


def _word_count(value: object) -> int:
    return len(re.findall(r'\w+', clean_cell(value), flags=re.UNICODE))


def _is_description_column(column: object) -> bool:
    key = _column_key(column)
    if not key:
        return False
    return any(signal in key for signal in DESCRIPTION_COLUMN_SIGNALS)


def _is_plain_description_column(column: object) -> bool:
    key = _column_key(column)
    return key in {_column_key(signal) for signal in PLAIN_DESCRIPTION_COLUMN_SIGNALS}


def _is_title_column(column: object) -> bool:
    key = _column_key(column)
    if not key:
        return False
    return any(signal == key or key.startswith(f'{signal}_') for signal in TITLE_COLUMN_SIGNALS)


def _is_fallback_title_column(column: object) -> bool:
    key = _column_key(column)
    if not key:
        return False
    return any(signal == key or key.startswith(f'{signal}_') for signal in FALLBACK_TITLE_COLUMN_SIGNALS)


def _best_title_column(df: pd.DataFrame, *, exclude: str = '') -> str:
    excluded = _column_key(exclude)
    for column in df.columns:
        if _column_key(column) == excluded:
            continue
        if _is_title_column(column) and not _is_description_column(column):
            return str(column)
    for column in df.columns:
        if _column_key(column) == excluded:
            continue
        if _is_fallback_title_column(column) and not _is_description_column(column):
            return str(column)
    return ''


def _looks_like_dirty_description(value: object) -> bool:
    text = clean_cell(value)
    if not text:
        return False

    key = _value_key(text)
    if any(normalize_key(signal) in key for signal in DESCRIPTION_NOISE_SIGNALS):
        return True

    return len(text) >= LONG_DESCRIPTION_MIN_CHARS and _word_count(text) >= LONG_DESCRIPTION_MIN_WORDS


def _description_columns_to_clean(df: pd.DataFrame) -> list[str]:
    columns: list[str] = []
    for column in df.columns:
        column_text = str(column)
        if _is_description_column(column_text):
            columns.append(column_text)
            continue

        if not _is_plain_description_column(column_text):
            continue

        series = df[column]
        try:
            should_clean = any(_looks_like_dirty_description(value) for value in series.tolist())
        except Exception:
            should_clean = False
        if should_clean:
            columns.append(column_text)
    return columns


def _clean_site_description_columns(df: pd.DataFrame, operation: str) -> pd.DataFrame:
    """Aplica a blindagem de descrição no fluxo unificado de busca por site."""
    _ = operation
    if not isinstance(df, pd.DataFrame) or df.empty:
        return df

    description_columns = _description_columns_to_clean(df)
    if not description_columns:
        return df

    out = df.copy().fillna('')
    for column in description_columns:
        if column not in out.columns:
            continue
        title_column = _best_title_column(out, exclude=column)
        for index, value in out[column].items():
            if _is_plain_description_column(column) and not _looks_like_dirty_description(value):
                continue
            title = str(out.at[index, title_column]) if title_column and title_column in out.columns else ''
            out.at[index, column] = clean_product_description(str(value or ''), title=title, limit=1600)
    return out.fillna('')


def run_pipeline(
    raw_urls: str,
    requested_columns: list[str] | None = None,
    all_products: bool = True,
    max_pages: int = ALL_PAGES_LIMIT,
    max_products: int = ALL_PRODUCTS_LIMIT,
    operation: str = 'universal',
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    selected_operation = _infer_operation_from_columns(operation, requested_columns)
    limits = normalize_capture_limits(max_pages=max_pages, max_products=max_products, mode='safe')
    selected_max_pages = _bounded_limit(limits['max_pages'], ALL_PAGES_LIMIT, SAFE_CAPTURE_MAX_PAGES)
    selected_max_products = _bounded_limit(limits['max_products'], ALL_PRODUCTS_LIMIT, SAFE_CAPTURE_MAX_PRODUCTS)

    if progress_callback:
        progress_callback({
            'stage': 'Preparando',
            'message': 'Preparando motor por modelo de destino com limite seguro...',
            'progress': 0.02,
            'operation': selected_operation,
            'max_pages': selected_max_pages,
            'max_products': selected_max_products,
            'all_products': False,
            'safe_limited': True,
        })

    df_result = run_site_operation_engine(
        operation=selected_operation,
        raw_urls=raw_urls,
        requested_columns=requested_columns,
        max_pages=selected_max_pages,
        max_products=selected_max_products,
        stop_early=True,
        progress_callback=progress_callback,
    )

    if progress_callback:
        progress_callback({'stage': 'Organizando', 'message': 'Organizando os dados conforme o modelo anexado...', 'progress': 0.96})
    cleaned_result = _clean_site_description_columns(df_result, selected_operation)
    safe = sanitize_for_bling(cleaned_result, operation=selected_operation)
    if progress_callback:
        progress_callback({'stage': 'Pronto', 'message': f'{len(safe)} produto(s) preparados na origem.', 'progress': 1.0})
    return safe


__all__ = ['run_pipeline']
