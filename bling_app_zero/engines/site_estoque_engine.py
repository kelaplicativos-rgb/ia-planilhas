from __future__ import annotations

import pandas as pd

from bling_app_zero.core.column_contract import build_contract
from bling_app_zero.core.text import normalize_key
from bling_app_zero.engines.flash_amplo_engine import run_flash_amplo_page_mode, scrape_urls, split_urls


DEFAULT_ESTOQUE_SITE_COLUMNS = [
    'Código',
    'Descrição',
    'Depósito (OBRIGATÓRIO)',
    'Balanço (OBRIGATÓRIO)',
]

APOIO_NAME_COLUMNS = [
    'Nome do produto',
    'Produto',
    'Descrição',
]


def _effective_columns(requested_columns: list[str] | None) -> list[str]:
    columns = [str(column).strip() for column in (requested_columns or []) if str(column).strip()]
    return columns or list(DEFAULT_ESTOQUE_SITE_COLUMNS)


def _has_description_contract(requested_columns: list[str]) -> bool:
    for field in build_contract(requested_columns):
        if field.kind in {'descricao', 'nome_apoio'}:
            return True
    return False


def _inject_optional_name_support(requested_columns: list[str]) -> list[str]:
    """Garante nome/descrição como apoio visual quando o modelo não pede nenhum nome.

    O motor de estoque por site continua orientado pelo contrato da planilha: o CSV final
    será gerado pelo pipeline de estoque usando o modelo anexado. Esta coluna extra serve
    apenas para o preview bruto e para ajudar o mapeamento quando necessário.
    """
    columns = list(requested_columns)
    if _has_description_contract(columns):
        return columns

    for candidate in APOIO_NAME_COLUMNS:
        if candidate not in columns:
            columns.append(candidate)
            break
    return columns


def _blank_missing_requested_columns(df: pd.DataFrame, requested_columns: list[str]) -> pd.DataFrame:
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()

    for column in requested_columns:
        if column not in out.columns:
            out[column] = ''

    return out.loc[:, requested_columns].fillna('')


def _remove_unrequested_product_noise(df: pd.DataFrame, requested_columns: list[str]) -> pd.DataFrame:
    """Remove colunas de cadastro que não fazem parte do contrato de estoque.

    Esse é o isolamento principal: estoque por site não herda campos de cadastro como
    GTIN, imagens, marca, categoria ou preço quando a planilha modelo não solicitar.
    """
    out = df.copy().fillna('') if isinstance(df, pd.DataFrame) else pd.DataFrame()
    requested_keys = {normalize_key(column) for column in requested_columns}

    keep_columns: list[str] = []
    for column in out.columns:
        if normalize_key(column) in requested_keys or column in requested_columns:
            keep_columns.append(column)

    if not keep_columns:
        return pd.DataFrame(columns=requested_columns)

    out = out.loc[:, keep_columns]
    return _blank_missing_requested_columns(out, requested_columns)


def run_site_estoque_engine(
    raw_urls: str,
    requested_columns: list[str] | None = None,
    all_products: bool = False,
    max_pages: int = 250,
    max_products: int = 1000,
) -> pd.DataFrame:
    model_columns = _effective_columns(requested_columns)
    extraction_columns = _inject_optional_name_support(model_columns)
    urls = split_urls(raw_urls)
    if not urls:
        return pd.DataFrame(columns=extraction_columns)

    if all_products:
        df = run_flash_amplo_page_mode(
            raw_urls=raw_urls,
            requested_columns=extraction_columns,
            max_pages=max_pages,
            max_products=max_products,
            keep_only_requested_columns=True,
        )
    else:
        df = scrape_urls(urls, requested_columns=extraction_columns)

    return _remove_unrequested_product_noise(df, extraction_columns)
