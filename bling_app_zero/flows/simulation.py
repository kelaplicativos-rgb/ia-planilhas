from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from bling_app_zero.flows.engine_registry import get_engine, registry_dataframe
from bling_app_zero.flows.estoque_contract import default_model as estoque_default_model


@dataclass(frozen=True)
class SimulationResult:
    flow: str
    ok: bool
    rows: int
    columns: int
    message: str


def _sample_source() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                'Código': 'ABC-001',
                'Descrição': 'Produto teste BLINGFLOW',
                'Preço': '19,90',
                'Estoque': '12',
                'GTIN/EAN': '7891234567895',
                'Marca': 'Marca Teste',
                'Categoria': 'Teste > Simulação',
                'URL Imagens': 'https://example.com/produto-a.jpg|https://example.com/produto-b.jpg',
            }
        ]
    )


def _cadastro_model() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            'Código',
            'Descrição',
            'Preço de venda',
            'GTIN/EAN',
            'Marca',
            'Categoria',
            'URL Imagens',
        ]
    )


def _result(flow: str, df: Any, message: str = 'OK') -> SimulationResult:
    if isinstance(df, tuple) and df:
        df = df[0]
    if isinstance(df, pd.DataFrame):
        return SimulationResult(flow=flow, ok=not df.empty or len(df.columns) > 0, rows=len(df), columns=len(df.columns), message=message)
    return SimulationResult(flow=flow, ok=False, rows=0, columns=0, message='Retorno inválido')


def simulate_cadastro_planilha() -> SimulationResult:
    engine = get_engine('cadastro_planilha')
    df_final, _mapping = engine.run(_sample_source(), _cadastro_model())
    return _result('Cadastro por planilha', df_final)


def simulate_estoque_planilha() -> SimulationResult:
    engine = get_engine('estoque_planilha')
    df_final, _mapping = engine.run(_sample_source(), estoque_default_model(), deposito='Não definido')
    return _result('Estoque por planilha', df_final)


def simulate_site_cadastro_contract() -> SimulationResult:
    engine = get_engine('site_cadastro')
    df_site = engine.run(
        'https://example.com/produto-teste',
        requested_columns=['URL', 'Código', 'Descrição', 'Preço', 'URL Imagens'],
        all_products=False,
        max_pages=10,
        max_products=1,
        operation='cadastro',
    )
    return _result('Site para cadastro', df_site, 'Contrato de site cadastro executado')


def simulate_site_estoque_contract() -> SimulationResult:
    engine = get_engine('site_estoque')
    df_site = engine.run(
        'https://example.com/produto-teste',
        requested_columns=['Código', 'Descrição', 'Depósito (OBRIGATÓRIO)', 'Balanço (OBRIGATÓRIO)'],
        all_products=False,
        max_pages=10,
        max_products=1,
        operation='estoque',
    )
    return _result('Site para estoque', df_site, 'Contrato de site estoque executado')


def simulate_pricing() -> SimulationResult:
    engine = get_engine('precificacao')
    df = engine.run(_sample_source(), 'Preço', 'Preço de venda', 30.0, 0.0, 0.0, 0.0, 0.0)
    return _result('Precificação', df)


def run_all_simulations() -> pd.DataFrame:
    simulations = [
        simulate_cadastro_planilha,
        simulate_estoque_planilha,
        simulate_site_cadastro_contract,
        simulate_site_estoque_contract,
        simulate_pricing,
    ]
    rows: list[dict[str, object]] = []
    for simulation in simulations:
        try:
            item = simulation()
        except Exception as exc:
            item = SimulationResult(flow=simulation.__name__, ok=False, rows=0, columns=0, message=str(exc))
        rows.append(
            {
                'Fluxo/Recurso': item.flow,
                'Status': 'OK' if item.ok else 'FALHA',
                'Linhas': item.rows,
                'Colunas': item.columns,
                'Mensagem': item.message,
            }
        )
    return pd.DataFrame(rows)


def run_engine_inventory() -> pd.DataFrame:
    return registry_dataframe()
