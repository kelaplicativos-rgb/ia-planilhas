from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from bling_app_zero.core.column_contract import build_contract
from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.flows.engine_registry import get_engine, registry_dataframe
from bling_app_zero.flows.estoque_contract import default_model as estoque_default_model
from bling_app_zero.v2.price_multistore.flow import run_multistore_price_flow
from bling_app_zero.v2.price_multistore.matcher import build_not_included_audit
from bling_app_zero.v2.store_profiles import build_store_profile


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


def _sample_source_extra_for_audit() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {'IdProduto': '1001', 'ID na Loja': 'MLB-001', 'Código': 'ABC-001', 'Descrição': 'Produto encontrado', 'Preço de custo': '20,00'},
            {'IdProduto': '9999', 'ID na Loja': 'MLB-FORA', 'Código': 'FORA-001', 'Descrição': 'Produto fora da planilha Bling', 'Preço de custo': '35,00'},
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


def _multistore_model() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                'IdProduto': '1001',
                'ID na Loja': 'MLB-001',
                'Nome': 'Produto encontrado',
                'Código': 'ABC-001',
                'Preco': '',
                'Preco Promocional': '',
                'ID do Fornecedor': '',
                'ID da Marca': '',
                'Link Externo': '',
                'Nome Loja (Multilojas)': 'Mercado Livre',
            }
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


def simulate_multistore_pricing() -> SimulationResult:
    model_df = _multistore_model()
    source_df = _sample_source_extra_for_audit()
    pricing_rules = {
        'calculator_mode': 'nominal_profit',
        'marketplace_fee_percent': 16.0,
        'commission_percent': 16.0,
        'tax_percent': 8.0,
        'freight_cost': 0.0,
        'other_sale_fees_percent': 0.0,
        'desired_nominal_profit': 15.0,
        'desired_contribution_margin_percent': 0.0,
        'desired_sale_price': 0.0,
        'supplier_term_days': 15.0,
        'stock_turnover_days': 30.0,
        'promo_discount_percent': 0.0,
    }
    profile = build_store_profile('mercado_livre', name='Mercado Livre', overrides={'pricing_rules': pricing_rules})
    result = run_multistore_price_flow(model_df, profile, source_df, 'Preço de custo', pricing_rules)
    df = result.payload.df if result.payload is not None else pd.DataFrame()
    audit_df = build_not_included_audit(model_df, source_df, 'Preço de custo')
    ok = bool(result.ok) and isinstance(df, pd.DataFrame) and not df.empty and isinstance(audit_df, pd.DataFrame) and len(audit_df) == 1
    return SimulationResult(
        flow='Preços multiloja',
        ok=ok,
        rows=len(df) if isinstance(df, pd.DataFrame) else 0,
        columns=len(df.columns) if isinstance(df, pd.DataFrame) else 0,
        message='Multiloja calculou preço e gerou auditoria de item não incluído' if ok else f'Multiloja falhou: {result.message}',
    )


SIMULATION_REGISTRY: dict[str, tuple[str, Callable[[], SimulationResult]]] = {
    'cadastro_arquivo': ('Cadastro por arquivo', simulate_cadastro_planilha),
    'estoque_arquivo': ('Estoque por arquivo', simulate_estoque_planilha),
    'site_cadastro': ('Site para cadastro', simulate_site_cadastro_contract),
    'site_estoque': ('Site para estoque', simulate_site_estoque_contract),
    'precificacao': ('Precificação', simulate_pricing),
    'precos_multiloja': ('Preços multiloja', simulate_multistore_pricing),
}


def _row_from_result(item: SimulationResult) -> dict[str, object]:
    return {
        'Fluxo/Recurso': item.flow,
        'Status': 'OK' if item.ok else 'FALHA',
        'Linhas': item.rows,
        'Colunas': item.columns,
        'Mensagem': item.message,
    }


def run_single_simulation(key: str) -> pd.DataFrame:
    label, simulation = SIMULATION_REGISTRY.get(key, (key, None))
    if simulation is None:
        item = SimulationResult(flow=label, ok=False, rows=0, columns=0, message='Simulação não encontrada')
        return pd.DataFrame([_row_from_result(item)])
    try:
        item = simulation()
    except Exception as exc:
        item = SimulationResult(flow=label, ok=False, rows=0, columns=0, message=str(exc))
    return pd.DataFrame([_row_from_result(item)])


def run_all_simulations() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for key in SIMULATION_REGISTRY:
        result_df = run_single_simulation(key)
        rows.extend(result_df.to_dict('records'))
    return pd.DataFrame(rows)


def simulation_options() -> list[tuple[str, str]]:
    return [(key, value[0]) for key, value in SIMULATION_REGISTRY.items()]


def run_engine_inventory() -> pd.DataFrame:
    return registry_dataframe()


__all__ = [
    'SIMULATION_REGISTRY',
    'run_all_simulations',
    'run_engine_inventory',
    'run_single_simulation',
    'simulation_options',
]
