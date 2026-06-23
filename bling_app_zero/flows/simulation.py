from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import pandas as pd

from bling_app_zero.core.column_contract import build_contract
from bling_app_zero.core.exporter import sanitize_for_bling
from bling_app_zero.core.final_csv_exporter import normalize_image_columns
from bling_app_zero.core.provisional_category import DEFAULT_PROVISIONAL_CATEGORY, apply_category_guard_to_payload
from bling_app_zero.core.xml_nfe_runtime_patch import NFE_COST_COLUMN, _apply_nfe_unit_cost
from bling_app_zero.engines.estoque_engine import _status_to_quantity
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


def simulate_estoque_status_site() -> SimulationResult:
    available = _status_to_quantity('Produto disponível em estoque')
    out = _status_to_quantity('Produto esgotado')
    ok = available == '10' and out == '0'
    return SimulationResult('Estoque status do site', ok, 2, 2, f'disponível={available}; esgotado={out}')


def simulate_images_csv_export() -> SimulationResult:
    raw = '|'.join(
        [
            'https://example.com/produto-1.jpg',
            'https://example.com/logo.png',
            'https://example.com/produto-2.webp',
            'https://example.com/produto-3.jpg',
            'https://example.com/produto-4.jpg',
            'https://example.com/produto-5.jpg',
            'https://example.com/produto-6.jpg',
            'https://example.com/produto-7.jpg',
        ]
    )
    df = normalize_image_columns(pd.DataFrame([{'URL Imagens': raw}]))
    images = str(df.at[0, 'URL Imagens']).split('|') if not df.empty else []
    ok = len(images) == 6 and all('logo' not in image.lower() for image in images)
    return SimulationResult('Imagens CSV final', ok, len(df), len(df.columns), f'{len(images)} imagem(ns) válidas após limpeza/limite')


def simulate_xml_nfe_unit_cost() -> SimulationResult:
    row = _apply_nfe_unit_cost(
        {
            'qCom': '2,0000',
            'vProd': '100,00',
            'vFrete': '10,00',
            'vSeg': '4,00',
            'vOutro': '6,00',
            'vDesc': '0,00',
            'imposto.ICMS.ICMS00.vICMS': '18,00',
            'imposto.IPI.IPITrib.vIPI': '2,00',
        }
    )
    ok = row.get(NFE_COST_COLUMN) == '70,00'
    return SimulationResult('XML NFe custo unitário', ok, 1, len(row), f"{NFE_COST_COLUMN}={row.get(NFE_COST_COLUMN, '')}")


def simulate_category_guard() -> SimulationResult:
    result = apply_category_guard_to_payload({}, row={'Descrição': 'Produto sem pista segura XYZ'}, meta={}, category_id_resolver=None)
    category = result.payload.get('categoria') if isinstance(result.payload, dict) else {}
    category_text = str(category.get('descricao') if isinstance(category, dict) else category or '')
    ok = bool(category_text) and (category_text == DEFAULT_PROVISIONAL_CATEGORY or not result.provisional)
    return SimulationResult('Categoria obrigatória/fallback', ok, 1, 1, f'categoria={category_text}; provisoria={result.provisional}')


def simulate_brand_imenso_runtime() -> SimulationResult:
    try:
        from bling_app_zero.core.brand_runtime_patch import install_brand_runtime_patch
        from bling_app_zero.core import bling_direct_sender_smart as smart

        install_brand_runtime_patch()
        brand = smart._resolve_brand('Caixa de Som Imenso Bluetooth Portátil', '')
    except Exception as exc:
        return SimulationResult('Marca inteligente Imenso', False, 0, 0, str(exc))
    ok = brand == 'Imenso'
    return SimulationResult('Marca inteligente Imenso', ok, 1, 1, f'marca={brand}')


SIMULATION_REGISTRY: dict[str, tuple[str, Callable[[], SimulationResult]]] = {
    'cadastro_arquivo': ('Cadastro por arquivo', simulate_cadastro_planilha),
    'estoque_arquivo': ('Estoque por arquivo', simulate_estoque_planilha),
    'site_cadastro': ('Site para cadastro', simulate_site_cadastro_contract),
    'site_estoque': ('Site para estoque', simulate_site_estoque_contract),
    'precificacao': ('Precificação', simulate_pricing),
    'precos_multiloja': ('Preços multiloja', simulate_multistore_pricing),
    'estoque_status_site': ('Estoque status do site', simulate_estoque_status_site),
    'imagens_csv_final': ('Imagens CSV final', simulate_images_csv_export),
    'xml_nfe_custo_unitario': ('XML NFe custo unitário', simulate_xml_nfe_unit_cost),
    'categoria_obrigatoria_fallback': ('Categoria obrigatória/fallback', simulate_category_guard),
    'marca_imenso': ('Marca inteligente Imenso', simulate_brand_imenso_runtime),
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
