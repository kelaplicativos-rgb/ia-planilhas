from __future__ import annotations

import importlib
from pathlib import Path

import pandas as pd


def test_universal_modules_import() -> None:
    for module_name in [
        'bling_app_zero.universal.model_detector',
        'bling_app_zero.universal.universal_contract',
        'bling_app_zero.universal.output_builder',
    ]:
        importlib.import_module(module_name)


def test_model_detector_detects_stock_price_and_custom_models() -> None:
    from bling_app_zero.universal.model_detector import detect_model_type

    estoque = pd.DataFrame(columns=['SKU', 'Depósito', 'Quantidade', 'Saldo'])
    precos = pd.DataFrame(columns=['SKU', 'Preço de venda', 'Preço promocional', 'Desconto'])
    multilojas = pd.DataFrame(columns=['SKU', 'Loja', 'Marketplace', 'Preço loja 1'])
    custom = pd.DataFrame(columns=['Campo A', 'Campo B'])

    assert detect_model_type(estoque).model_type == 'estoque'
    assert detect_model_type(precos).model_type == 'precos'
    assert detect_model_type(multilojas).model_type == 'multilojas'
    assert detect_model_type(custom).model_type == 'personalizado'


def test_universal_output_preserves_exact_model_columns_and_order() -> None:
    from bling_app_zero.universal.output_builder import build_universal_output

    source = pd.DataFrame(
        [
            {'Produto': 'Cabo USB', 'Valor': '19,90', 'Qtd': '5', 'Extra': 'ignorar'},
            {'Produto': 'Fonte 20W', 'Valor': '49,90', 'Qtd': '2', 'Extra': 'ignorar'},
        ]
    )
    model = pd.DataFrame(columns=['Nome final', 'Preço final', 'Estoque final', 'Coluna vazia'])
    mapping = {
        'Nome final': 'Produto',
        'Preço final': 'Valor',
        'Estoque final': 'Qtd',
    }

    output = build_universal_output(source, model, mapping)

    assert list(output.columns) == ['Nome final', 'Preço final', 'Estoque final', 'Coluna vazia']
    assert list(output['Nome final']) == ['Cabo USB', 'Fonte 20W']
    assert list(output['Preço final']) == ['19,90', '49,90']
    assert list(output['Estoque final']) == ['5', '2']
    assert list(output['Coluna vazia']) == ['', '']
    assert 'Extra' not in output.columns


def test_home_models_shows_universal_detection_language() -> None:
    home_models = Path('bling_app_zero/ui/home_models.py').read_text(encoding='utf-8')

    assert 'detect_model_type' in home_models
    assert 'cadastro, estoque, preços, multilojas ou personalizado' in home_models
    assert 'planilha final ainda respeitará exatamente as colunas e a ordem' in home_models
