from __future__ import annotations

import pandas as pd

from bling_app_zero.core.spreadsheet_mapping_center import (
    apply_mapping,
    build_mapping_state,
    build_request_from_frames,
    simulate_universal_mapping_request,
)


def test_universal_mapping_request_accepts_pandas_index_columns() -> None:
    source = pd.DataFrame(
        {
            'SKU': ['ABC-1'],
            'Produto': ['Produto teste'],
            'Preço': ['R$ 10,00'],
            'Estoque': ['5'],
        }
    )
    model = pd.DataFrame(columns=['Código', 'Descrição', 'Preço unitário', 'Estoque'])

    request = build_request_from_frames(source, model, operation='universal', signature='pytest')

    assert request.operation == 'universal'
    assert request.source_columns == ('SKU', 'Produto', 'Preço', 'Estoque')
    assert request.target_columns == ('Código', 'Descrição', 'Preço unitário', 'Estoque')


def test_universal_flow_mapping_and_output_simulation() -> None:
    result = simulate_universal_mapping_request()

    assert result['ok'] is True
    assert result['operation'] == 'universal'
    assert result['mapped_fields'] >= 4
    assert result['rows'] == 1
    assert result['columns'] == 5
    assert result['descricao_from_produto_blocked'] is True
    assert result['mapping']['Descrição'] == 'Título real'


def test_semantic_mapping_blocks_header_when_content_disagrees() -> None:
    source = pd.DataFrame(
        {
            'Produto': ['7891234567890', '7891234567891'],
            'Nome correto': ['Mouse Gamer RGB', 'Teclado Bluetooth'],
        }
    )
    model = pd.DataFrame(columns=['Descrição', 'GTIN'])

    request = build_request_from_frames(source, model, operation='universal', signature='pytest-semantic')
    mapping = {
        'Descrição': 'Produto',
        'GTIN': 'Produto',
    }

    state = build_mapping_state(request, mapping, source=source, engine='local_test')
    rows = {row['Contrato final']: row for row in state.rows}

    assert state.state.mapping['Descrição'] == 'Produto'
    assert '🔴' in rows['Descrição']['Farol']
    assert rows['Descrição']['Leitura IA'] == 'gtin'
    assert 'Alerta IA' in rows['Descrição']

    assert '🔴' not in rows['GTIN']['Farol']


def test_bling_api_like_flow_uses_same_safe_mapping_core() -> None:
    source = pd.DataFrame(
        {
            'codigo': ['SKU-1'],
            'descricao': ['Produto API'],
            'preco': ['19.90'],
            'estoque': ['7'],
        }
    )
    model = pd.DataFrame(columns=['Código', 'Descrição', 'Preço unitário', 'Estoque'])
    request = build_request_from_frames(source, model, operation='bling_api_cadastro', signature='pytest-api')
    mapping = {
        'Código': 'codigo',
        'Descrição': 'descricao',
        'Preço unitário': 'preco',
        'Estoque': 'estoque',
    }

    state = build_mapping_state(request, mapping, source=source, engine='local_test')
    output = apply_mapping(source, model, state.state.mapping)

    assert request.operation == 'bling_api_cadastro'
    assert output.shape == (1, 4)
    assert output.loc[0, 'Código'] == 'SKU-1'
    assert output.loc[0, 'Descrição'] == 'Produto API'


def test_price_multistore_like_flow_uses_same_safe_mapping_core() -> None:
    source = pd.DataFrame(
        {
            'SKU': ['P-1'],
            'Custo': ['10.00'],
            'Preço Loja A': ['15.90'],
            'Preço Loja B': ['17.90'],
        }
    )
    model = pd.DataFrame(columns=['Código', 'Preço Loja A', 'Preço Loja B'])
    request = build_request_from_frames(source, model, operation='price_multistore', signature='pytest-price')
    mapping = {
        'Código': 'SKU',
        'Preço Loja A': 'Preço Loja A',
        'Preço Loja B': 'Preço Loja B',
    }

    state = build_mapping_state(request, mapping, source=source, engine='local_test')
    output = apply_mapping(source, model, state.state.mapping)

    assert request.operation == 'price_multistore'
    assert output.shape == (1, 3)
    assert output.loc[0, 'Preço Loja A'] == '15.90'
    assert output.loc[0, 'Preço Loja B'] == '17.90'
