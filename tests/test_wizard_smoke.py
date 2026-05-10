from __future__ import annotations

import importlib

import pandas as pd


CRITICAL_MODULES = [
    'bling_app_zero.ui.home_wizard',
    'bling_app_zero.ui.cadastro_wizard_steps',
    'bling_app_zero.ui.estoque_wizard_steps',
    'bling_app_zero.ui.cadastro_mapping',
    'bling_app_zero.ui.site_panel',
    'bling_app_zero.ui.site_outputs',
    'bling_app_zero.flows.site_as_source',
    'bling_app_zero.ui.wizard_state_guard',
    'bling_app_zero.core.exporter',
    'bling_app_zero.core.gtin',
]


def test_critical_wizard_modules_import() -> None:
    for module_name in CRITICAL_MODULES:
        importlib.import_module(module_name)


def test_gtin_invalid_values_are_cleaned() -> None:
    from bling_app_zero.core.gtin import clean_gtin

    assert clean_gtin('123') == ''
    assert clean_gtin('0000000000000') == ''
    assert clean_gtin('abc789') == ''


def test_exporter_uses_bling_csv_contract() -> None:
    from bling_app_zero.core.exporter import to_bling_csv_bytes

    df = pd.DataFrame(
        [
            {
                'Descrição': 'Produto teste',
                'GTIN/EAN': '123',
                'URL imagens externas': 'https://a.com/1.jpg, https://a.com/2.jpg',
            }
        ]
    )
    csv_bytes = to_bling_csv_bytes(df)
    text = csv_bytes.decode('utf-8-sig')

    assert ';' in text
    assert ',' not in text.splitlines()[0]
    assert 'https://a.com/1.jpg|https://a.com/2.jpg' in text

    body = text.splitlines()[1]
    columns = text.splitlines()[0].split(';')
    values = body.split(';')
    row = dict(zip(columns, values))
    assert row['GTIN/EAN'] == ''
