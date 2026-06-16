from __future__ import annotations

import pandas as pd

from bling_app_zero.core.final_measure_unit_defaults import apply_measure_unit_default_resource
from bling_app_zero.core.final_output_rule_engine import apply_final_output_rules


def test_final_measure_unit_default_fills_existing_column() -> None:
    df = pd.DataFrame([
        {'Produto': 'A', 'Unidade das medidas': ''},
        {'Produto': 'B', 'Unidade das medidas': 'cm'},
        {'Produto': 'C', 'Unidade das medidas': 'Metros'},
    ])

    result = apply_measure_unit_default_resource(df, {'measure_unit_name_default': 'Centimetros', 'custom_rules': []})

    assert result.columns == ('Unidade das medidas',)
    assert result.changed == 2
    assert result.df['Unidade das medidas'].tolist()[0] == 'Centímetros'
    assert result.df['Unidade das medidas'].tolist()[1] == 'Centímetros'
    assert result.df['Unidade das medidas'].tolist()[2] == 'Metros'


def test_final_output_rules_apply_measure_unit_before_download_or_api() -> None:
    df = pd.DataFrame([{'Produto': 'A', 'Unidade de medida': ''}])

    fixed_df, report = apply_final_output_rules(df, context='download')

    assert report.measure_unit_columns == ('Unidade de medida',)
    assert report.measure_unit_cells_changed == 1
    assert fixed_df['Unidade de medida'].tolist() == ['Centímetros']


def test_final_measure_unit_does_not_add_missing_column() -> None:
    df = pd.DataFrame([{'Codigo': 'ABC', 'Preco': '10'}])

    fixed_df, report = apply_final_output_rules(df, context='download')

    assert list(fixed_df.columns) == ['Codigo', 'Preco']
    assert report.measure_unit_columns == tuple()
    assert report.measure_unit_cells_changed == 0
