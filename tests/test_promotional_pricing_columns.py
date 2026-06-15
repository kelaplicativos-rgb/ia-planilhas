from __future__ import annotations

import unittest

import pandas as pd

from bling_app_zero.core.product_pricing_center import apply_price_calculator_plugin, promotional_price_columns


class TestPromotionalPricingColumns(unittest.TestCase):
    def test_detects_common_promotional_column_names(self) -> None:
        columns = [
            'Código',
            'Preço normal',
            'Preço oferta',
            'Valor promocional',
            'Preço especial',
            'Preço com desconto',
        ]

        detected = promotional_price_columns(columns)

        self.assertEqual(
            detected,
            ['Preço oferta', 'Valor promocional', 'Preço especial', 'Preço com desconto'],
        )

    def test_does_not_detect_regular_or_cost_prices_as_promotional(self) -> None:
        detected = promotional_price_columns(['Preço', 'Preço de custo', 'Valor de compra'])

        self.assertEqual(detected, [])

    def test_plugin_fills_original_promotional_column_from_model(self) -> None:
        source = pd.DataFrame(
            {
                'Código': ['A', 'B'],
                'Custo': ['100,00', '200,00'],
                'Preço oferta': ['', ''],
            }
        )
        config = {
            'enabled': True,
            'quick_reprice_mode': 'markup',
            'quick_markup_percent': 20,
            'promo_discount_percent': 10,
        }

        result = apply_price_calculator_plugin(
            source,
            enabled=True,
            config=config,
            cost_column='Custo',
        )

        self.assertTrue(result.applied)
        self.assertIn('Preço de venda', result.df.columns)
        self.assertIn('Preço promocional', result.df.columns)
        self.assertIn('Preço oferta', result.df.columns)
        self.assertTrue(result.df['Preço oferta'].astype(str).str.strip().ne('').all())
        self.assertEqual(
            result.df['Preço oferta'].astype(str).tolist(),
            result.df['Preço promocional'].astype(str).tolist(),
        )


if __name__ == '__main__':
    unittest.main()
