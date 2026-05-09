from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd


@dataclass(frozen=True)
class SiteEngineConfig:
    operation: str
    title: str
    description: str
    button_label: str
    output_filename: str
    default_max_pages: int
    default_max_products: int
    required_model: bool


def normalize_site_operation(operation: str | None) -> str:
    text = str(operation or '').strip().lower()
    if text in {'estoque', 'stock', 'atualizacao_estoque', 'atualização de estoque', 'estoque_site'}:
        return 'estoque'
    return 'cadastro'


def config_for_site_operation(operation: str | None) -> SiteEngineConfig:
    normalized = normalize_site_operation(operation)
    if normalized == 'estoque':
        return SiteEngineConfig(
            operation='estoque',
            title='Criar origem de estoque pelo site',
            description='Busca somente as colunas pedidas pelo modelo de estoque. O que não for encontrado fica vazio.',
            button_label='Buscar no site e criar origem de estoque',
            output_filename='origem_site_estoque.csv',
            default_max_pages=80,
            default_max_products=300,
            required_model=True,
        )
    return SiteEngineConfig(
        operation='cadastro',
        title='Criar origem de cadastro pelo site',
        description='Busca produtos no site do fornecedor e monta uma origem para gerar o CSV de cadastro.',
        button_label='Buscar no site e criar origem de cadastro',
        output_filename='origem_site_cadastro.csv',
        default_max_pages=120,
        default_max_products=300,
        required_model=False,
    )


def run_site_engine(
    *,
    operation: str,
    pipeline: Callable[..., pd.DataFrame],
    raw_urls: str,
    requested_columns: list[str] | None,
    all_products: bool,
    max_pages: int,
    max_products: int,
    progress_callback: Callable[[dict], None] | None = None,
) -> pd.DataFrame:
    normalized = normalize_site_operation(operation)
    return pipeline(
        raw_urls,
        requested_columns=requested_columns,
        all_products=all_products,
        max_pages=max_pages,
        max_products=max_products,
        operation=normalized,
        progress_callback=progress_callback,
    )
