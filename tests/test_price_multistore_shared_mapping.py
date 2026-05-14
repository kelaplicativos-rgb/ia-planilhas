from __future__ import annotations

import pandas as pd

from bling_app_zero.v2.price_multistore.flow import COST_COLUMN_INTERNAL, prepare_multistore_table
from bling_app_zero.v2.price_multistore.matcher import build_not_included_audit, merge_source_cost


def test_multistore_merge_uses_manual_identifier_columns() -> None:
    model_df = pd.DataFrame(
        [
            {'ID na Loja': 'ML-001', 'IdProduto': '10', 'Preço': ''},
            {'ID na Loja': 'ML-002', 'IdProduto': '20', 'Preço': ''},
        ]
    )
    source_df = pd.DataFrame(
        [
            {'SKU fornecedor': 'ML-001', 'Custo fornecedor': '12,50'},
            {'SKU fornecedor': 'ML-002', 'Custo fornecedor': '18,90'},
        ]
    )

    out = merge_source_cost(
        model_df,
        source_df,
        source_cost_column='Custo fornecedor',
        model_identifier_column='ID na Loja',
        source_identifier_column='SKU fornecedor',
    )

    assert COST_COLUMN_INTERNAL in out.columns
    assert out[COST_COLUMN_INTERNAL].tolist() == ['12,50', '18,90']
    assert 'SKU fornecedor' not in out.columns


def test_multistore_does_not_fallback_to_automatic_identifier_mapping() -> None:
    model_df = pd.DataFrame([{'ID na Loja': 'ML-001', 'IdProduto': '10', 'Preço': ''}])
    source_df = pd.DataFrame([{'ID na Loja': 'ML-001', 'Custo fornecedor': '12,50'}])

    out = merge_source_cost(
        model_df,
        source_df,
        source_cost_column='Custo fornecedor',
        model_identifier_column='',
        source_identifier_column='',
    )

    assert COST_COLUMN_INTERNAL in out.columns
    assert out[COST_COLUMN_INTERNAL].tolist() == ['']


def test_multistore_prepare_table_keeps_model_when_source_missing() -> None:
    model_df = pd.DataFrame([{'ID na Loja': 'ML-001', 'IdProduto': '10', 'Preço': ''}])

    out = prepare_multistore_table(model_df, None, source_cost_column='Custo fornecedor')

    assert COST_COLUMN_INTERNAL in out.columns
    assert out[COST_COLUMN_INTERNAL].tolist() == ['']
    assert [column for column in model_df.columns if column in out.columns] == list(model_df.columns)


def test_multistore_audit_respects_manual_identifier_columns() -> None:
    model_df = pd.DataFrame([{'ID na Loja': 'ML-001', 'IdProduto': '10', 'Preço': ''}])
    source_df = pd.DataFrame(
        [
            {'SKU fornecedor': 'ML-001', 'Custo fornecedor': '12,50'},
            {'SKU fornecedor': 'ML-999', 'Custo fornecedor': '99,90'},
        ]
    )

    audit = build_not_included_audit(
        model_df,
        source_df,
        source_cost_column='Custo fornecedor',
        model_identifier_column='ID na Loja',
        source_identifier_column='SKU fornecedor',
    )

    assert len(audit) == 1
    assert audit.iloc[0]['Valor do identificador'] == 'ML-999'
    assert audit.iloc[0]['Coluna origem'] == 'SKU fornecedor'
    assert audit.iloc[0]['Coluna Bling'] == 'ID na Loja'
