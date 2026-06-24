from __future__ import annotations

import pandas as pd

from bling_app_zero.core.final_output_engine import build_final_output
from bling_app_zero.core.universal_smart_rules import (
    DEFAULT_WEIGHT_VALUE,
    apply_universal_smart_rules,
    default_smart_rules_config,
    normalize_smart_rules_config,
    rule_managed_source_mapping,
    rule_managed_target_columns,
)


def test_smart_rules_apply_only_explicit_toggles() -> None:
    df = pd.DataFrame(
        {
            'Codigo': [' P001 '],
            'Descricao': ['Produto\ncom   espaco'],
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
    assert output.loc[0, 'Codigo'] == 'P001'
    assert output.loc[0, 'Descricao'] == 'Produto com espaco'
    assert output.loc[0, 'URL Imagens Externas'] == 'https://a/img1.jpg|https://a/img2.jpg'
    assert output.loc[0, 'GTIN/EAN'] == ''
    assert report['image_columns'] == ['URL Imagens Externas']
    assert report['gtin_columns'] == ['GTIN/EAN']


def test_enabled_group_without_specific_toggles_keeps_values_unchanged() -> None:
    df = pd.DataFrame(
        {
            'URL Imagens Externas': ['https://a/1.jpg,https://a/2.jpg,https://a/2.jpg,https://a/3.jpg'],
            'Unidade': [''],
            'Situacao': [''],
        }
    )

    output, report = apply_universal_smart_rules(df, {'enabled': True})

    assert output.equals(df.fillna(''))
    assert report['applied_cells'] == 0
    assert report['image_columns'] == []
    assert report['fixed_columns'] == []


def test_smart_rules_defaults_are_opt_in() -> None:
    defaults = default_smart_rules_config()

    assert defaults['enabled'] is False
    assert defaults['clean_text'] is False
    assert defaults['normalize_images'] is False
    assert defaults['dedupe_images'] is False
    assert defaults['limit_images'] is False
    assert defaults['validate_gtin'] is False
    assert defaults['fill_category_aliases'] is False
    assert defaults['apply_unit_default'] is False
    assert defaults['apply_measure_unit_default'] is False
    assert defaults['apply_status_default'] is False
    assert defaults['apply_condition_default'] is False
    assert defaults['apply_dimensions_default'] is False
    assert defaults['apply_weight_default'] is True
    assert defaults['net_weight_value'] == DEFAULT_WEIGHT_VALUE
    assert defaults['gross_weight_value'] == DEFAULT_WEIGHT_VALUE
    assert defaults['max_images'] == 6


def test_smart_rules_disabled_keeps_values_unchanged() -> None:
    df = pd.DataFrame({'Descricao': ['Produto\ncom   espaco'], 'GTIN/EAN': ['1234567890123']})

    output, report = apply_universal_smart_rules(df, {'enabled': False, 'clean_text': True, 'validate_gtin': True})

    assert output.equals(df.fillna(''))
    assert report['enabled'] is False
    assert report['applied_cells'] == 0


def test_final_output_applies_rules_only_when_toggle_enabled() -> None:
    source = pd.DataFrame({'SKU': [' P001 '], 'Nome': ['Caneca\nAzul'], 'Fotos': ['url1|url1|url2|url3']})
    model = pd.DataFrame(columns=['Codigo', 'Descricao', 'URL Imagens Externas'])
    mapping = {'Codigo': 'SKU', 'Descricao': 'Nome', 'URL Imagens Externas': 'Fotos'}
    config = {'enabled': True, 'clean_text': True, 'normalize_images': True, 'dedupe_images': True, 'limit_images': True, 'max_images': 2}

    with_rules = build_final_output(source, model, mapping, run_smart_features=True, smart_rules_config=config)
    without_rules = build_final_output(source, model, mapping, run_smart_features=False, smart_rules_config=config)

    assert with_rules.output is not None
    assert without_rules.output is not None
    assert with_rules.output.loc[0, 'Codigo'] == 'P001'
    assert with_rules.output.loc[0, 'Descricao'] == 'Caneca Azul'
    assert with_rules.output.loc[0, 'URL Imagens Externas'] == 'url1|url2'
    assert without_rules.output.loc[0, 'URL Imagens Externas'] == 'url1|url1|url2|url3'
    assert with_rules.output.columns.tolist() == model.columns.tolist()


def test_category_alias_only_runs_with_specific_toggle() -> None:
    source = pd.DataFrame({'SKU': ['P001'], 'Nome': ['Fone Bluetooth'], 'Categoria': ['Fones']})
    model = pd.DataFrame(columns=['Codigo', 'Descricao', 'Categoria do produto'])
    mapping = {'Codigo': 'SKU', 'Descricao': 'Nome', 'Categoria do produto': ''}

    alias_off = build_final_output(source, model, mapping, run_smart_features=True, smart_rules_config={'enabled': True})
    alias_on = build_final_output(source, model, mapping, run_smart_features=True, smart_rules_config={'enabled': True, 'fill_category_aliases': True})

    assert alias_off.output is not None
    assert alias_on.output is not None
    assert alias_off.output.loc[0, 'Categoria do produto'] == ''
    assert alias_on.output.loc[0, 'Categoria do produto'] == 'Fones'


def test_optional_default_toggles_fill_empty_matching_columns() -> None:
    df = pd.DataFrame({'Unidade': [''], 'Unidade de medida': [''], 'Situacao': [''], 'Condicao': [''], 'Altura': [''], 'Largura': [''], 'Profundidade': [''], 'Nome': ['Produto']})

    output, report = apply_universal_smart_rules(
        df,
        {
            'enabled': True,
            'apply_unit_default': True,
            'unit_value': 'UN',
            'apply_measure_unit_default': True,
            'measure_unit_value': 'Centimetros',
            'apply_status_default': True,
            'status_value': 'Ativo',
            'apply_condition_default': True,
            'condition_value': 'Novo',
            'apply_dimensions_default': True,
            'height_value': '2',
            'width_value': '11',
            'depth_value': '16',
        },
    )

    assert output.loc[0, 'Unidade'] == 'UN'
    assert output.loc[0, 'Unidade de medida'] == 'Centimetros'
    assert output.loc[0, 'Situacao'] == 'Ativo'
    assert output.loc[0, 'Condicao'] == 'Novo'
    assert output.loc[0, 'Altura'] == '2'
    assert output.loc[0, 'Largura'] == '11'
    assert output.loc[0, 'Profundidade'] == '16'
    assert output.loc[0, 'Nome'] == 'Produto'
    assert report['applied_cells'] == 7


def test_weight_defaults_fill_both_weight_columns() -> None:
    config = normalize_smart_rules_config({'enabled': True})
    df = pd.DataFrame({'Peso líquido (Kg)': [''], 'Peso bruto (Kg)': [''], 'Nome': ['Produto']})

    output, report = apply_universal_smart_rules(df, config)

    assert output.loc[0, 'Peso líquido (Kg)'] == DEFAULT_WEIGHT_VALUE
    assert output.loc[0, 'Peso bruto (Kg)'] == DEFAULT_WEIGHT_VALUE
    assert output.loc[0, 'Nome'] == 'Produto'
    assert {'column': 'Peso líquido (Kg)', 'rule': 'net_weight'} in report['fixed_columns']
    assert {'column': 'Peso bruto (Kg)', 'rule': 'gross_weight'} in report['fixed_columns']


def test_rule_managed_target_columns_returns_fixed_rule_fields_only() -> None:
    config = normalize_smart_rules_config(
        {
            'enabled': True,
            'apply_unit_default': True,
            'apply_status_default': True,
            'apply_condition_default': True,
            'apply_dimensions_default': True,
            'apply_weight_default': True,
        }
    )

    locked = rule_managed_target_columns(
        [
            'Descricao',
            'Unidade',
            'Situacao',
            'Condicao',
            'Altura',
            'Largura',
            'Profundidade',
            'Peso líquido (Kg)',
            'Peso bruto (Kg)',
        ],
        config,
    )

    assert locked == [
        'Unidade',
        'Situacao',
        'Condicao',
        'Altura',
        'Largura',
        'Profundidade',
        'Peso líquido (Kg)',
        'Peso bruto (Kg)',
    ]


def test_rule_fields_preserve_filled_rows_and_fill_only_blank_cells() -> None:
    config = normalize_smart_rules_config(
        {
            'enabled': True,
            'apply_unit_default': True,
            'unit_value': 'UN',
            'apply_measure_unit_default': True,
            'measure_unit_value': 'Centimetros',
            'apply_weight_default': True,
        }
    )
    source = pd.DataFrame(
        {
            'Unidade': ['CX', ''],
            'Unidade de medida': ['Metros', ''],
            'Peso líquido (Kg)': ['0.750', ''],
            'Peso bruto (Kg)': ['0.900', ''],
        }
    )
    model = pd.DataFrame(columns=['Unidade', 'Unidade de medida', 'Peso líquido (Kg)', 'Peso bruto (Kg)'])
    hidden_mapping = rule_managed_source_mapping(source.columns, model.columns, config)

    result = build_final_output(source, model, hidden_mapping, run_smart_features=True, smart_rules_config=config)

    assert hidden_mapping == {
        'Unidade': 'Unidade',
        'Unidade de medida': 'Unidade de medida',
        'Peso líquido (Kg)': 'Peso líquido (Kg)',
        'Peso bruto (Kg)': 'Peso bruto (Kg)',
    }
    assert result.output is not None
    assert result.output.loc[0, 'Unidade'] == 'CX'
    assert result.output.loc[1, 'Unidade'] == 'UN'
    assert result.output.loc[0, 'Unidade de medida'] == 'Metros'
    assert result.output.loc[1, 'Unidade de medida'] == 'Centimetros'
    assert result.output.loc[0, 'Peso líquido (Kg)'] == '0.750'
    assert result.output.loc[1, 'Peso líquido (Kg)'] == DEFAULT_WEIGHT_VALUE
    assert result.output.loc[0, 'Peso bruto (Kg)'] == '0.900'
    assert result.output.loc[1, 'Peso bruto (Kg)'] == DEFAULT_WEIGHT_VALUE
