from __future__ import annotations

import unittest

import pandas as pd

from bling_app_zero.core.bling_api_send_guard import validate_before_bling_send
from bling_app_zero.core.validators import price_validation_details, validate_final_df, validate_price_update_values


class TestPriceUpdateValidation(unittest.TestCase):
    def test_accepts_positive_prices_in_brazilian_and_numeric_formats(self) -> None:
        df = pd.DataFrame(
            {
                'Código': ['A', 'B', 'C'],
                'Preço': ['220', 'R$ 1.234,56', 506.0],
            }
        )

        self.assertEqual(validate_price_update_values(df), [])
        self.assertEqual(validate_final_df(df, 'atualizacao_preco'), [])

    def test_blocks_zero_blank_and_invalid_prices(self) -> None:
        df = pd.DataFrame(
            {
                'Código': ['A', 'B', 'C', 'D'],
                'Preço': ['0', '', 'texto', '15,90'],
            }
        )

        details = price_validation_details(df)
        errors = validate_price_update_values(df)

        self.assertEqual(details['invalid_rows'], [1, 2, 3])
        self.assertEqual(details['invalid_count'], 3)
        self.assertEqual(len(errors), 1)
        self.assertIn('3 produto(s)', errors[0])
        self.assertIn('Linhas: 1, 2, 3', errors[0])

    def test_ignores_cost_and_bling_destination_metadata_as_sale_price(self) -> None:
        df = pd.DataFrame(
            {
                'Código': ['A'],
                'Preço de custo': ['25,00'],
                'Bling preço destino': ['Preço geral'],
            }
        )

        errors = validate_price_update_values(df)

        self.assertEqual(len(errors), 1)
        self.assertIn('nenhuma coluna de preço de venda', errors[0])

    def test_api_guard_blocks_before_send_when_any_price_is_zero(self) -> None:
        df = pd.DataFrame(
            {
                'Código': ['A', 'B'],
                'Preço': ['10,00', '0'],
                'Bling preço destino': ['Preço geral', 'Preço geral'],
                'Bling canal venda id': ['', ''],
            }
        )

        result = validate_before_bling_send(df, 'atualizacao_preco')

        self.assertFalse(result.ok)
        self.assertEqual(result.status, 'BLOQUEADO')
        self.assertEqual(result.details['invalid_price_count'], 1)
        self.assertTrue(any('preço vazio, inválido ou igual a zero' in message for message in result.messages))

    def test_api_guard_accepts_valid_general_prices(self) -> None:
        df = pd.DataFrame(
            {
                'Código': ['A', 'B'],
                'Preço': ['10,00', '20.50'],
                'Bling preço destino': ['Preço geral', 'Preço geral'],
                'Bling canal venda id': ['', ''],
            }
        )

        result = validate_before_bling_send(df, 'atualizacao_preco')

        self.assertTrue(result.ok)
        self.assertEqual(result.details['invalid_price_count'], 0)


if __name__ == '__main__':
    unittest.main()
