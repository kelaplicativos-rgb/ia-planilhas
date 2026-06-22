from __future__ import annotations

from decimal import Decimal

import pandas as pd

from bling_app_zero.ui.shared_calculator import (
    apply_marketplace_calculation,
    build_marketplace_preview,
    default_base_price_column,
    default_price_target_column,
    manual_target_columns,
    price_target_columns,
)


def test_price_target_columns_prefers_model_price_fields() -> None:
    model = pd.DataFrame(columns=['Código', 'Descrição', 'Preço de venda', 'Estoque'])

    assert price_target_columns(model) == ['Preço de venda']
    assert default_price_target_column(model) == 'Preço de venda'


def test_default_price_target_avoids_cost_column_when_sale_column_exists() -> None:
    model = pd.DataFrame(columns=['Preço de custo', 'Valor venda', 'Preço promocional'])

    assert default_price_target_column(model) == 'Valor venda'


def test_price_target_columns_blocks_technical_recovery_columns() -> None:
    model = pd.DataFrame(columns=['Arquivo', 'Status', 'Conteúdo extraído'])

    assert price_target_columns(model) == []
    assert manual_target_columns(model) == []
    assert default_price_target_column(model) == ''


def test_manual_target_columns_keeps_real_model_columns_when_price_name_is_unusual() -> None:
    model = pd.DataFrame(columns=['Código', 'Descrição', 'Venda Final'])

    assert manual_target_columns(model) == ['Código', 'Descrição', 'Venda Final']


def test_default_base_price_column_prefers_cost_over_stock() -> None:
    source = pd.DataFrame({'Estoque': ['10', '12'], 'Custo fornecedor': ['20,00', '30,00'], 'Código': ['1', '2']})

    assert default_base_price_column(source) == 'Custo fornecedor'


def test_marketplace_calculation_can_write_directly_to_model_price_column() -> None:
    source = pd.DataFrame({'Custo fornecedor': ['50,00']})

    output = apply_marketplace_calculation(
        source,
        base_column='Custo fornecedor',
        output_column='Preço de venda',
        margin_percent=Decimal('50'),
        fee_percent=Decimal('0'),
        fixed_value=Decimal('0'),
    )

    assert output.loc[0, 'Preço de venda'] == '100,00'
    assert output.columns.tolist() == ['Custo fornecedor', 'Preço de venda']


def test_marketplace_preview_shows_before_after_and_difference() -> None:
    source = pd.DataFrame(
        {
            'Código': ['P001'],
            'Nome': ['Fone Bluetooth'],
            'Preço de custo': ['50,00'],
        }
    )

    preview = build_marketplace_preview(
        source,
        base_column='Preço de custo',
        output_column='Preço',
        margin_percent=Decimal('50'),
        fee_percent=Decimal('0'),
        fixed_value=Decimal('0'),
    )

    assert preview.columns.tolist() == ['Código/SKU', 'Produto', 'Antes (Preço de custo)', 'Depois (Preço)', 'Diferença']
    assert preview.loc[0, 'Código/SKU'] == 'P001'
    assert preview.loc[0, 'Produto'] == 'Fone Bluetooth'
    assert preview.loc[0, 'Antes (Preço de custo)'] == '50,00'
    assert preview.loc[0, 'Depois (Preço)'] == '100,00'
    assert preview.loc[0, 'Diferença'] == '50,00'
