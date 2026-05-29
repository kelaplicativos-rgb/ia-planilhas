from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from bling_app_zero.engines.fast_site_scraper.constants import normalize_capture_limits


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


UNIVERSAL_ALIASES = {'universal', 'modelo', 'modelo_destino', 'planilha', 'wizard_cadastro_estoque'}


def normalize_site_operation(operation: str | None) -> str:
    text = str(operation or '').strip().lower()
    if text in {'estoque', 'stock', 'atualizacao_estoque', 'atualização de estoque', 'estoque_site'}:
        return 'estoque'
    if text in {'cadastro', 'cadastro_site', 'produtos', 'produto'}:
        return 'cadastro'
    if text in UNIVERSAL_ALIASES:
        return 'universal'
    return 'universal'


def config_for_site_operation(operation: str | None) -> SiteEngineConfig:
    normalized = normalize_site_operation(operation)
    if normalized == 'estoque':
        return SiteEngineConfig(
            operation='estoque',
            title='Entrada por site para estoque',
            description='Busca no site somente os campos pedidos pelo modelo escolhido. O que não for encontrado fica vazio.',
            button_label='Buscar no site e gerar origem de estoque',
            output_filename='origem_site_estoque.csv',
            default_max_pages=80,
            default_max_products=100,
            required_model=True,
        )
    if normalized == 'cadastro':
        return SiteEngineConfig(
            operation='cadastro',
            title='Entrada por site',
            description='Busca dados no site do fornecedor para preencher o modelo escolhido no mapeamento.',
            button_label='Buscar no site e gerar origem',
            output_filename='origem_site.csv',
            default_max_pages=80,
            default_max_products=100,
            required_model=False,
        )
    return SiteEngineConfig(
        operation='universal',
        title='Entrada por site',
        description='Busca no site os campos pedidos pelo modelo anexado e gera uma origem unica.',
        button_label='Buscar no site e gerar origem unica',
        output_filename='origem_site_universal.csv',
        default_max_pages=80,
        default_max_products=100,
        required_model=True,
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
    limits = normalize_capture_limits(
        max_pages=max_pages,
        max_products=max_products,
        mode='deep' if not all_products else 'safe',
    )
    return pipeline(
        raw_urls,
        requested_columns=requested_columns,
        all_products=False,
        max_pages=limits['max_pages'],
        max_products=limits['max_products'],
        operation=normalized,
        progress_callback=progress_callback,
    )
