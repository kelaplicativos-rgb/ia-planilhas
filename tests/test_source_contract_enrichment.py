from __future__ import annotations

import unittest

import pandas as pd

from bling_app_zero.core.source_contract_enrichment import enrich_source_with_requested_columns


class TestSourceContractEnrichment(unittest.TestCase):
    def test_fills_requested_model_columns_from_origin_aliases(self) -> None:
        source = pd.DataFrame([
            {
                'SKU': 'ABC-1',
                'Título': 'Produto A',
                'EAN': '7891234567895',
                'Preço unitário (OBRIGATÓRIO)': 'R$ 19,90',
                'Marca': 'Marca A',
            }
        ])
        requested = ['Código', 'Descrição', 'GTIN/EAN', 'Preço', 'Marca']

        enriched = enrich_source_with_requested_columns(source, requested, source='test')

        self.assertEqual(enriched.loc[0, 'Código'], 'ABC-1')
        self.assertEqual(enriched.loc[0, 'Descrição'], 'Produto A')
        self.assertEqual(enriched.loc[0, 'GTIN/EAN'], '7891234567895')
        self.assertEqual(enriched.loc[0, 'Preço'], 'R$ 19,90')
        self.assertEqual(enriched.loc[0, 'Marca'], 'Marca A')

    def test_does_not_create_values_when_not_available(self) -> None:
        source = pd.DataFrame([{'SKU': 'ABC-1', 'Título': 'Produto A'}])
        enriched = enrich_source_with_requested_columns(source, ['NCM', 'CEST', 'GTIN/EAN'], source='test')

        self.assertNotIn('NCM', enriched.columns)
        self.assertNotIn('CEST', enriched.columns)
        self.assertNotIn('GTIN/EAN', enriched.columns)

    def test_extracts_labeled_gtin_from_text_when_column_is_missing(self) -> None:
        source = pd.DataFrame([{'SKU': 'ABC-1', 'Texto bruto': 'Produto A EAN: 7891234567895'}])
        enriched = enrich_source_with_requested_columns(source, ['GTIN/EAN'], source='test')

        self.assertEqual(enriched.loc[0, 'GTIN/EAN'], '7891234567895')


if __name__ == '__main__':
    unittest.main()
