from __future__ import annotations

import unittest

import pandas as pd

from bling_app_zero.engines.estoque_engine import MissingEstoqueModelError, run_estoque_engine


class TestEstoqueFluxo(unittest.TestCase):
    def test_estoque_exige_modelo_real(self) -> None:
        origem = pd.DataFrame({'Código': ['P001'], 'Quantidade': ['10']})

        with self.assertRaises(MissingEstoqueModelError):
            run_estoque_engine(origem, None, deposito='Principal')

        with self.assertRaises(MissingEstoqueModelError):
            run_estoque_engine(origem, pd.DataFrame(), deposito='Principal')

    def test_estoque_gera_somente_colunas_do_modelo(self) -> None:
        origem = pd.DataFrame(
            {
                'SKU': ['P001'],
                'Nome': ['Produto apoio'],
                'Saldo': ['15'],
                'Preço': ['99,90'],
            }
        )
        modelo = pd.DataFrame(columns=['Código', 'Depósito (OBRIGATÓRIO)', 'Balanço (OBRIGATÓRIO)'])

        final, mapping = run_estoque_engine(origem, modelo, deposito='Galpão 1')

        self.assertEqual(list(final.columns), ['Código', 'Depósito (OBRIGATÓRIO)', 'Balanço (OBRIGATÓRIO)'])
        self.assertEqual(final.loc[0, 'Código'], 'P001')
        self.assertEqual(final.loc[0, 'Depósito (OBRIGATÓRIO)'], 'Galpão 1')
        self.assertEqual(final.loc[0, 'Balanço (OBRIGATÓRIO)'], '15')
        self.assertNotIn('Nome', final.columns)
        self.assertNotIn('Preço', final.columns)
        self.assertEqual(mapping['Balanço (OBRIGATÓRIO)'], 'Saldo')

    def test_estoque_nao_mapeia_preco_como_quantidade(self) -> None:
        origem = pd.DataFrame({'SKU': ['P001'], 'Preço de venda': ['199,90']})
        modelo = pd.DataFrame(columns=['Código', 'Balanço (OBRIGATÓRIO)'])

        final, mapping = run_estoque_engine(origem, modelo, deposito='Principal')

        self.assertEqual(final.loc[0, 'Código'], 'P001')
        self.assertEqual(final.loc[0, 'Balanço (OBRIGATÓRIO)'], '')
        self.assertEqual(mapping['Balanço (OBRIGATÓRIO)'], '')


if __name__ == '__main__':
    unittest.main()
