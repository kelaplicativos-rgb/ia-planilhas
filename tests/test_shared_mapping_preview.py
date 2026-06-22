from __future__ import annotations

import pandas as pd

from bling_app_zero.ui.shared_mapping import _sample_values, confidence_flag


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
