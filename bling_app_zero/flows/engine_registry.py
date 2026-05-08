from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd


@dataclass(frozen=True)
class EngineResource:
    key: str
    title: str
    description: str
    operation: str
    loader: Callable[[], Callable]

    def run(self, *args, **kwargs):
        engine = self.loader()
        return engine(*args, **kwargs)


def _load_cadastro_pipeline() -> Callable:
    from bling_app_zero.pipelines.cadastro_pipeline import run_pipeline

    return run_pipeline


def _load_estoque_pipeline() -> Callable:
    from bling_app_zero.pipelines.estoque_pipeline import run_pipeline

    return run_pipeline


def _load_site_pipeline() -> Callable:
    from bling_app_zero.pipelines.site_pipeline import run_pipeline

    return run_pipeline


def _load_pricing_engine() -> Callable:
    from bling_app_zero.core.pricing import apply_pricing

    return apply_pricing


ENGINE_REGISTRY: dict[str, EngineResource] = {
    'cadastro_planilha': EngineResource(
        key='cadastro_planilha',
        title='Cadastro de Produtos por Planilha/XML/PDF',
        description='Motor independente para transformar origem tabular em CSV de cadastro Bling.',
        operation='cadastro',
        loader=_load_cadastro_pipeline,
    ),
    'estoque_planilha': EngineResource(
        key='estoque_planilha',
        title='Atualização de Estoque por Planilha',
        description='Motor independente para transformar origem tabular em CSV de estoque Bling.',
        operation='estoque',
        loader=_load_estoque_pipeline,
    ),
    'site_cadastro': EngineResource(
        key='site_cadastro',
        title='Busca por Site para Cadastro',
        description='Motor de captura por site orientado ao cadastro de produtos.',
        operation='cadastro',
        loader=_load_site_pipeline,
    ),
    'site_estoque': EngineResource(
        key='site_estoque',
        title='Busca por Site para Estoque',
        description='Motor de captura por site orientado somente ao contrato da planilha de estoque.',
        operation='estoque',
        loader=_load_site_pipeline,
    ),
    'precificacao': EngineResource(
        key='precificacao',
        title='Precificação Inteligente',
        description='Motor independente de cálculo de preço antes do mapeamento final.',
        operation='pricing',
        loader=_load_pricing_engine,
    ),
}


def get_engine(key: str) -> EngineResource:
    if key not in ENGINE_REGISTRY:
        raise KeyError(f'Motor não registrado: {key}')
    return ENGINE_REGISTRY[key]


def list_engines() -> list[EngineResource]:
    return list(ENGINE_REGISTRY.values())


def registry_dataframe() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                'Motor': engine.key,
                'Fluxo': engine.operation,
                'Título': engine.title,
                'Descrição': engine.description,
            }
            for engine in list_engines()
        ]
    )
