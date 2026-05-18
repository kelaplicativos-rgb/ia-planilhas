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
    if text in {'cadastro', 'cadastro_site', 'produtos', 'produto'}:
        return 'cadastro'
    return ''


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
            default_max_products=300,
            required_model=True,
        )
    return SiteEngineConfig(
        operation='cadastro',
        title='Entrada por site',
        description='Busca dados no site do fornecedor para preencher o modelo escolhido no mapeamento.',
        button_label='Buscar no site e gerar origem',
        output_filename='origem_site.csv',
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
    if normalized not in {'cadastro', 'estoque'}:
        raise ValueError('Operação por site não definida. Escolha Cadastro ou Estoque antes de buscar no site.')
    return pipeline(
        raw_urls,
        requested_columns=requested_columns,
        all_products=all_products,
        max_pages=max_pages,
        max_products=max_products,
        operation=normalized,
        progress_callback=progress_callback,
    )
