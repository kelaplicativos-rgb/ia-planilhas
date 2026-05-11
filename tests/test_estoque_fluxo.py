from __future__ import annotations

import unittest
from pathlib import Path

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

    def test_simulacao_estoque_arquivo_e_site_usam_mesmo_contrato_do_bling(self) -> None:
        modelo = pd.DataFrame(columns=['Código', 'Depósito (OBRIGATÓRIO)', 'Balanço (OBRIGATÓRIO)'])
        origem_arquivo = pd.DataFrame({'SKU': ['ARQ-001'], 'Quantidade': ['8'], 'Produto': ['Produto arquivo']})
        origem_site = pd.DataFrame({'Código': ['SITE-001'], 'Estoque': ['3'], 'Nome': ['Produto site'], 'Preço': ['50,00']})

        final_arquivo, mapping_arquivo = run_estoque_engine(origem_arquivo, modelo, deposito='Central')
        final_site, mapping_site = run_estoque_engine(origem_site, modelo, deposito='Central')

        self.assertEqual(list(final_arquivo.columns), list(modelo.columns))
        self.assertEqual(list(final_site.columns), list(modelo.columns))
        self.assertEqual(final_arquivo.loc[0, 'Código'], 'ARQ-001')
        self.assertEqual(final_site.loc[0, 'Código'], 'SITE-001')
        self.assertEqual(final_arquivo.loc[0, 'Depósito (OBRIGATÓRIO)'], 'Central')
        self.assertEqual(final_site.loc[0, 'Depósito (OBRIGATÓRIO)'], 'Central')
        self.assertEqual(final_arquivo.loc[0, 'Balanço (OBRIGATÓRIO)'], '8')
        self.assertEqual(final_site.loc[0, 'Balanço (OBRIGATÓRIO)'], '3')
        self.assertNotIn('Produto', final_arquivo.columns)
        self.assertNotIn('Nome', final_site.columns)
        self.assertNotIn('Preço', final_site.columns)
        self.assertEqual(mapping_arquivo['Balanço (OBRIGATÓRIO)'], 'Quantidade')
        self.assertEqual(mapping_site['Balanço (OBRIGATÓRIO)'], 'Estoque')

    def test_estoque_site_panel_usa_assinatura_atual_do_save_site_source(self) -> None:
        source = Path('bling_app_zero/ui/estoque_site_panel.py').read_text(encoding='utf-8')

        self.assertIn('save_site_source(', source)
        self.assertIn('df_modelo_cadastro=None', source)
        self.assertIn('df_modelo_estoque=df_modelo_estoque', source)
        self.assertIn('df_modelo=df_modelo_estoque', source)
        self.assertNotIn('cadastro_model_df=', source)
        self.assertNotIn('estoque_model_df=', source)
        self.assertNotIn('operation_model_df=', source)


if __name__ == '__main__':
    unittest.main()
