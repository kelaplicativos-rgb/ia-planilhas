from __future__ import annotations

import csv
import importlib
from io import StringIO
from pathlib import Path

import pandas as pd


LIGHT_CRITICAL_MODULES = [
    'bling_app_zero.ui.home_wizard',
    'bling_app_zero.ui.cadastro_wizard_steps',
    'bling_app_zero.ui.estoque_wizard_steps',
    'bling_app_zero.ui.cadastro_mapping',
    'bling_app_zero.flows.site_as_source',
    'bling_app_zero.ui.wizard_state_guard',
    'bling_app_zero.core.exporter',
    'bling_app_zero.core.gtin',
]

SITE_CRITICAL_MODULES = [
    'bling_app_zero.ui.site_panel',
    'bling_app_zero.ui.site_outputs',
]


def test_light_critical_wizard_modules_import() -> None:
    for module_name in LIGHT_CRITICAL_MODULES:
        importlib.import_module(module_name)


def test_site_critical_modules_import_without_running_scraper() -> None:
    for module_name in SITE_CRITICAL_MODULES:
        importlib.import_module(module_name)


def test_mapping_css_uses_existing_theme_variables() -> None:
    mapping_css = Path('bling_app_zero/ui/layout/mapping.py').read_text(encoding='utf-8')

    assert '--bling-panel' not in mapping_css
    assert 'var(--bling-success)' not in mapping_css
    assert '--bling-surface' in mapping_css
    assert '--bling-success-text' in mapping_css


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
    rows = list(csv.reader(StringIO(text), delimiter=';'))

    assert len(rows) == 2
    header = rows[0]
    values = rows[1]
    row = dict(zip(header, values))

    assert 'Descrição' in header
    assert 'GTIN/EAN' in header
    assert 'URL imagens externas' in header
    assert row['GTIN/EAN'] == ''
    assert row['URL imagens externas'] == 'https://a.com/1.jpg|https://a.com/2.jpg'
