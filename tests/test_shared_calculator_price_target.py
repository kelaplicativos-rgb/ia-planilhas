from __future__ import annotations

from decimal import Decimal

import pandas as pd

from bling_app_zero.ui.shared_calculator import (
    apply_marketplace_calculation,
    default_base_price_column,
    default_price_target_column,
    price_target_columns,
)


def test_price_target_columns_prefers_model_price_fields() -> None:
    model = pd.DataFrame(columns=['Código', 'Descrição', 'Preço de venda', 'Estoque'])

    assert price_target_columns(model) == ['Preço de venda']
    assert default_price_target_column(model) == 'Preço de venda'


def test_default_price_target_avoids_cost_column_when_sale_column_exists() -> None:
    model = pd.DataFrame(columns=['Preço de custo', 'Valor venda', 'Preço promocional'])

    assert default_price_target_column(model) == 'Valor venda'


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
