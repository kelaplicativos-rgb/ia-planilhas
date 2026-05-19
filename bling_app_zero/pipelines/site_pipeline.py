from __future__ import annotations

import re
from typing import Callable

import pandas as pd

from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.core.text import clean_cell, normalize_key
from bling_app_zero.engines.fast_site_scraper.text_cleaner import clean_product_description
from bling_app_zero.engines.site_operations import run_site_operation_engine


VALID_OPERATIONS = {'cadastro', 'estoque', 'universal'}
UNIVERSAL_ALIASES = {'universal', 'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}
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
    value = str(operation or 'universal').strip().lower()
    if value in {'estoque', 'stock', 'atualizacao_estoque', 'atualização de estoque', 'estoque_site'}:
        return 'estoque'
    if value in {'cadastro', 'cadastro_site', 'produtos', 'produto'}:
        return 'cadastro'
    if value in UNIVERSAL_ALIASES:
        return 'universal'
    return 'universal'


def _column_key(column: object) -> str:
    return normalize_key(str(column or '').replace('\n', ' ').replace('\r', ' ')).replace(' ', '_')


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

    # Quando o site despeja o bloco inteiro da página dentro da coluna "Descrição",
    # geralmente vem como parágrafo grande. Produto curto legítimo não deve ser mexido.
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
    """Aplica a blindagem de descrição no fluxo unificado de busca por site.

    BLINGFIX:
    - antes a limpeza só pegava colunas como "Descrição complementar";
    - depois ainda havia uma trava por operação "estoque";
    - como o fluxo atual é unificado e o tipo de modelo não é mais separado pelo
      usuário, a limpeza passa a valer para qualquer operação recebida;
    - a proteção continua segura porque só limpa "Descrição" simples quando há
      ruído conhecido ou texto longo de página, preservando descrição curta.
    """
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
    selected_operation = _normalize_operation(operation)
    selected_max_pages = max(max_pages or 0, ALL_PAGES_LIMIT) if all_products else max_pages
    selected_max_products = max(max_products or 0, ALL_PRODUCTS_LIMIT) if all_products else max_products

    if progress_callback:
        progress_callback({
            'stage': 'Preparando',
            'message': 'Preparando motor por modelo de destino...',
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