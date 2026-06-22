from __future__ import annotations

import pandas as pd

from bling_app_zero.core.final_output_engine import build_final_output
from bling_app_zero.core.universal_smart_rules import apply_universal_smart_rules, default_smart_rules_config


def test_smart_rules_clean_text_images_and_gtin_without_changing_columns() -> None:
    df = pd.DataFrame(
        {
            'Código': [' P001 '],
            'Descrição': ['Produto\ncom   espaço'],
            'URL Imagens Externas': ['https://a/img1.jpg|https://a/img1.jpg|https://a/img2.jpg|https://a/img3.jpg'],
            'GTIN/EAN': ['1234567890123'],
        }
    )
    config = {
        'enabled': True,
        'clean_text': True,
        'remove_empty_markers': True,
        'normalize_images': True,
        'dedupe_images': True,
        'limit_images': True,
        'max_images': 2,
        'validate_gtin': True,
    }

    output, report = apply_universal_smart_rules(df, config)

    assert output.columns.tolist() == df.columns.tolist()
    assert output.loc[0, 'Código'] == 'P001'
    assert output.loc[0, 'Descrição'] == 'Produto com espaço'
    assert output.loc[0, 'URL Imagens Externas'] == 'https://a/img1.jpg|https://a/img2.jpg'
    assert output.loc[0, 'GTIN/EAN'] == ''
    assert report['applied_cells'] >= 4
    assert report['image_columns'] == ['URL Imagens Externas']
    assert report['gtin_columns'] == ['GTIN/EAN']


def test_smart_rules_comma_separated_bling_images_are_split_deduped_and_limited() -> None:
    df = pd.DataFrame(
        {
            'URL Imagens Externas': [
                'https://app.sistemab2drop.com.br/uploads/1.webp,'
                'https://app.sistemab2drop.com.br/uploads/2.webp,'
                'https://app.sistemab2drop.com.br/uploads/2.webp,'
                'https://app.sistemab2drop.com.br/uploads/3.webp,'
                'https://app.sistemab2drop.com.br/uploads/4.webp,'
                'https://app.sistemab2drop.com.br/uploads/5.webp,'
                'https://app.sistemab2drop.com.br/uploads/6.webp,'
                'https://app.sistemab2drop.com.br/uploads/7.webp'
            ]
        }
    )

    output, report = apply_universal_smart_rules(df, {'enabled': True})

    assert output.loc[0, 'URL Imagens Externas'] == (
        'https://app.sistemab2drop.com.br/uploads/1.webp|'
        'https://app.sistemab2drop.com.br/uploads/2.webp|'
        'https://app.sistemab2drop.com.br/uploads/3.webp|'
        'https://app.sistemab2drop.com.br/uploads/4.webp|'
        'https://app.sistemab2drop.com.br/uploads/5.webp|'
        'https://app.sistemab2drop.com.br/uploads/6.webp'
    )
    assert report['image_columns'] == ['URL Imagens Externas']
    assert report['limit_images'] is True
    assert report['max_images'] == 6


def test_smart_rules_default_limits_images_to_six() -> None:
    defaults = default_smart_rules_config()

    assert defaults['limit_images'] is True
    assert defaults['max_images'] == 6


def test_smart_rules_disabled_keeps_values_unchanged() -> None:
    df = pd.DataFrame({'Descrição': ['Produto\ncom   espaço'], 'GTIN/EAN': ['1234567890123']})

    output, report = apply_universal_smart_rules(df, {'enabled': False, 'clean_text': True, 'validate_gtin': True})

    assert output.equals(df.fillna(''))
    assert report['enabled'] is False
    assert report['applied_cells'] == 0


def test_final_output_applies_rules_only_when_toggle_enabled() -> None:
    source = pd.DataFrame({'SKU': [' P001 '], 'Nome': ['Caneca\nAzul'], 'Fotos': ['url1|url1|url2|url3']})
    model = pd.DataFrame(columns=['Código', 'Descrição', 'URL Imagens Externas'])
    mapping = {'Código': 'SKU', 'Descrição': 'Nome', 'URL Imagens Externas': 'Fotos'}
    config = {'enabled': True, 'clean_text': True, 'normalize_images': True, 'dedupe_images': True, 'limit_images': True, 'max_images': 2}

    with_rules = build_final_output(source, model, mapping, run_smart_features=True, smart_rules_config=config)
    without_rules = build_final_output(source, model, mapping, run_smart_features=False, smart_rules_config=config)

    assert with_rules.output is not None
    assert without_rules.output is not None
    assert with_rules.output.loc[0, 'Código'] == 'P001'
    assert with_rules.output.loc[0, 'Descrição'] == 'Caneca Azul'
    assert with_rules.output.loc[0, 'URL Imagens Externas'] == 'url1|url2'
    assert without_rules.output.loc[0, 'URL Imagens Externas'] == 'url1|url1|url2|url3'
    assert with_rules.output.columns.tolist() == model.columns.tolist()


def test_final_output_fills_categoria_do_produto_from_safe_category_alias_when_rules_are_enabled() -> None:
    source = pd.DataFrame({'SKU': ['P001'], 'Nome': ['Fone Bluetooth'], 'Categoria': ['Fones de ouvido']})
    model = pd.DataFrame(columns=['Código', 'Descrição', 'Categoria do produto'])
    mapping = {'Código': 'SKU', 'Descrição': 'Nome', 'Categoria do produto': ''}

    with_rules = build_final_output(source, model, mapping, run_smart_features=True, smart_rules_config={'enabled': True})
    without_rules = build_final_output(source, model, mapping, run_smart_features=False, smart_rules_config={'enabled': False})

    assert with_rules.output is not None
    assert without_rules.output is not None
    assert with_rules.output.loc[0, 'Categoria do produto'] == 'Fones de ouvido'
    assert without_rules.output.loc[0, 'Categoria do produto'] == ''
    assert with_rules.output.columns.tolist() == model.columns.tolist()
