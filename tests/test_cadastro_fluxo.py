from __future__ import annotations

import unittest

import pandas as pd

from bling_app_zero.engines.cadastro_engine import run_cadastro_engine


class TestCadastroFluxo(unittest.TestCase):
    def test_cadastro_mapeia_campos_principais_do_modelo(self) -> None:
        origem = pd.DataFrame(
            {
                'SKU': ['P001'],
                'Nome do Produto': ['Mouse Gamer'],
                'Valor Venda': ['59,90'],
                'EAN': ['7891234567895'],
                'Marca': ['Mega'],
                'Categoria': ['Informática > Mouse'],
            }
        )
        modelo = pd.DataFrame(columns=['Código', 'Descrição', 'Preço de venda', 'GTIN/EAN', 'Marca', 'Categoria'])

        final, mapping = run_cadastro_engine(origem, modelo)

        self.assertEqual(list(final.columns), list(modelo.columns))
        self.assertEqual(final.loc[0, 'Código'], 'P001')
        self.assertEqual(final.loc[0, 'Descrição'], 'Mouse Gamer')
        self.assertEqual(final.loc[0, 'Preço de venda'], '59,90')
        self.assertEqual(final.loc[0, 'GTIN/EAN'], '7891234567895')
        self.assertEqual(final.loc[0, 'Marca'], 'Mega')
        self.assertEqual(final.loc[0, 'Categoria'], 'Informática > Mouse')
        self.assertEqual(mapping['Código'], 'SKU')

    def test_cadastro_mantem_coluna_vazia_quando_origem_nao_tem_dado(self) -> None:
        origem = pd.DataFrame({'SKU': ['P001'], 'Nome': ['Produto sem NCM']})
        modelo = pd.DataFrame(columns=['Código', 'Descrição', 'NCM'])

        final, mapping = run_cadastro_engine(origem, modelo)

        self.assertEqual(final.loc[0, 'Código'], 'P001')
        self.assertEqual(final.loc[0, 'Descrição'], 'Produto sem NCM')
        self.assertEqual(final.loc[0, 'NCM'], '')
        self.assertEqual(mapping['NCM'], '')


if __name__ == '__main__':
    unittest.main()
