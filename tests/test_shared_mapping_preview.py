from __future__ import annotations

import pandas as pd

from bling_app_zero.ui.shared_mapping import (
    _sample_values,
    confidence_flag,
    decode_fixed_value,
    encode_fixed_value,
    is_fixed_value,
)
from bling_app_zero.universal.output_builder import build_universal_output


def test_sample_values_returns_unique_non_empty_preview_values() -> None:
    source = pd.DataFrame({'Descricao': ['Produto A', 'Produto A', '', None, 'Produto B', 'Produto C']})

    assert _sample_values(source, 'Descricao') == ['Produto A', 'Produto B', 'Produto C']


def test_sample_values_handles_missing_or_empty_column() -> None:
    source = pd.DataFrame({'Descricao': ['Produto A']})

    assert _sample_values(source, '') == []
    assert _sample_values(source, 'Inexistente') == []


def test_confidence_flag_for_empty_mapping() -> None:
    source = pd.DataFrame({'Descricao': ['Produto A']})

    assert confidence_flag('Descricao', '', source) == '🔴 vazio'


def test_confidence_flag_for_matching_mapping() -> None:
    source = pd.DataFrame({'Descricao': ['Produto A']})

    assert confidence_flag('Descricao', 'Descricao', source) == '🟢 alto'


def test_fixed_value_encoding_and_flag() -> None:
    encoded = encode_fixed_value('Depósito Principal')

    assert is_fixed_value(encoded) is True
    assert decode_fixed_value(encoded) == 'Depósito Principal'
    assert confidence_flag('Depósito', encoded, pd.DataFrame({'Descricao': ['Produto A']})) == '🟢 fixo'


def test_fixed_value_is_repeated_in_universal_output() -> None:
    source = pd.DataFrame({'SKU': ['A1', 'A2'], 'Descricao': ['Produto A', 'Produto B']})
    model = pd.DataFrame(columns=['Código', 'Descrição', 'Depósito', 'Unidade'])
    mapping = {
        'Código': 'SKU',
        'Descrição': 'Descricao',
        'Depósito': encode_fixed_value('Padrão'),
        'Unidade': encode_fixed_value('UN'),
    }

    output = build_universal_output(source, model, mapping)

    assert output['Depósito'].tolist() == ['Padrão', 'Padrão']
    assert output['Unidade'].tolist() == ['UN', 'UN']
