from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from bling_app_zero.core.column_contract import build_contract
from bling_app_zero.core.exporter import sanitize_for_bling
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
        has_structure = len(df.columns) > 0
        has_rows = len(df) > 0
        return SimulationResult(flow=flow, ok=has_structure and (has_rows or message.startswith('Contrato')), rows=len(df), columns=len(df.columns), message=message)
    return SimulationResult(flow=flow, ok=False, rows=0, columns=0, message='Retorno inválido')


def simulate_cadastro_planilha() -> SimulationResult:
    engine = get_engine('cadastro_planilha')
    df_final, _mapping = engine.run(_sample_source(), _cadastro_model())
    return _result('Cadastro por arquivo', sanitize_for_bling(df_final, operation='cadastro'), 'Cadastro gerou estrutura final')


def simulate_estoque_planilha() -> SimulationResult:
    engine = get_engine('estoque_planilha')
    df_final, _mapping = engine.run(_sample_source(), estoque_default_model(), deposito='Não definido')
    return _result('Estoque por arquivo', sanitize_for_bling(df_final, operation='estoque'), 'Estoque gerou estrutura final')


def _contract_dataframe(columns: list[str]) -> pd.DataFrame:
    contract = build_contract(columns)
    return pd.DataFrame(
        [
            {
                'Coluna solicitada': field.original,
                'Tipo': field.kind,
                'Obrigatório': field.required,
            }
            for field in contract
        ]
    )


def simulate_site_cadastro_contract() -> SimulationResult:
    columns = ['URL', 'Código', 'Descrição', 'Preço', 'URL Imagens']
    df_contract = _contract_dataframe(columns)
    return _result('Site para cadastro', df_contract, 'Contrato de site cadastro conferido offline')


def simulate_site_estoque_contract() -> SimulationResult:
    columns = ['Código', 'Descrição', 'Depósito (OBRIGATÓRIO)', 'Balanço (OBRIGATÓRIO)']
    df_contract = _contract_dataframe(columns)
    return _result('Site para estoque', df_contract, 'Contrato de site estoque conferido offline')


def simulate_pricing() -> SimulationResult:
    engine = get_engine('precificacao')
    df = engine.run(_sample_source(), 'Preço', 'Preço de venda', 30.0, 0.0, 0.0, 0.0, 0.0)
    ok = isinstance(df, pd.DataFrame) and 'Preço de venda' in df.columns and not df.empty
    return SimulationResult(flow='Precificação', ok=ok, rows=len(df) if isinstance(df, pd.DataFrame) else 0, columns=len(df.columns) if isinstance(df, pd.DataFrame) else 0, message='Preço calculado a partir da coluna de preço/custo')


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
