from __future__ import annotations

import unittest

import pandas as pd

from bling_app_zero.core.pricing import apply_pricing, calculate_price, detect_discount_percent, normalize_percent, to_number


class TestPrecificacaoFluxo(unittest.TestCase):
    def test_to_number_entende_formatos_brasileiros(self) -> None:
        self.assertEqual(to_number('R$ 1.234,56'), 1234.56)
        self.assertEqual(to_number('59,90'), 59.90)
        self.assertEqual(to_number('1.234'), 1234.0)
        self.assertEqual(to_number(''), 0.0)

    def test_normalize_percent(self) -> None:
        self.assertEqual(normalize_percent('0,2'), 20.0)
        self.assertEqual(normalize_percent('20%'), 20.0)

    def test_calculate_price_com_margens_e_limite(self) -> None:
        self.assertEqual(calculate_price(100, margin=20, tax=10, fee=5), 153.85)
        self.assertEqual(calculate_price(100, margin=100), 2000.0)
        self.assertEqual(calculate_price(100, margin=0, tax=0, fee=0), 100.0)

    def test_apply_pricing_cria_coluna_de_saida(self) -> None:
        df = pd.DataFrame({'Custo': ['100,00', '50,00']})

        out = apply_pricing(df, 'Custo', 'Preço unitário (OBRIGATÓRIO)', margin=20)

        self.assertIn('Preço unitário (OBRIGATÓRIO)', out.columns)
        self.assertEqual(out['Preço unitário (OBRIGATÓRIO)'].tolist(), [125.0, 62.5])

    def test_detect_discount_percent_por_coluna(self) -> None:
        df = pd.DataFrame({'Comissão %': ['12', '12', '10']})

        self.assertEqual(detect_discount_percent(df), 12.0)


if __name__ == '__main__':
    unittest.main()
