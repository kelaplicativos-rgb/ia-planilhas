from __future__ import annotations

import unittest

import pandas as pd

from bling_app_zero.core.exporter import sanitize_for_bling, to_bling_csv_bytes
from bling_app_zero.core.pricing import apply_pricing, calculate_price, to_number
from bling_app_zero.engines.cadastro_engine import run_cadastro_engine
from bling_app_zero.engines.estoque_engine import MissingEstoqueModelError, run_estoque_engine
from bling_app_zero.engines.fast_site_scraper.engine import run_fast_site_scraper
from bling_app_zero.ui.site_models import requested_columns_for_site_capture


class TestFluxosPrincipais(unittest.TestCase):
    def test_cadastro_por_planilha_mapeia_sanitiza_e_exporta_csv(self) -> None:
        origem = pd.DataFrame(
            {
                'sku': ['ABC-1'],
                'nome': ['Produto Teste'],
                'preco': ['R$ 10,90'],
                'ean': ['1234567890123'],
                'fotos': ['https://site.com/a.jpg, https://site.com/b.png'],
                'fornecedor': [''],
            }
        )
        modelo = pd.DataFrame(columns=['Código', 'Descrição', 'Preço de venda', 'GTIN/EAN', 'URL Imagens', 'Fornecedor'])

        final, mapping = run_cadastro_engine(origem, modelo)

        self.assertEqual(list(final.columns), list(modelo.columns))
        self.assertEqual(final.loc[0, 'Código'], 'ABC-1')
        self.assertEqual(final.loc[0, 'Descrição'], 'Produto Teste')
        self.assertEqual(final.loc[0, 'GTIN/EAN'], '1234567890123')
        self.assertEqual(final.loc[0, 'URL Imagens'], 'https://site.com/a.jpg|https://site.com/b.png')
        self.assertEqual(final.loc[0, 'Fornecedor'], 'Não definido')
        self.assertEqual(mapping['Código'], 'sku')

        csv_bytes = to_bling_csv_bytes(final)
        csv_text = csv_bytes.decode('utf-8-sig')
        self.assertIn(';', csv_text)
        self.assertIn('Produto Teste', csv_text)

    def test_precificacao_calcula_e_cria_coluna_de_preco(self) -> None:
        origem = pd.DataFrame({'custo': ['100,00']})

        precificado = apply_pricing(
            origem,
            cost_column='custo',
            output_column='Preço unitário (OBRIGATÓRIO)',
            margin=20,
            tax=10,
            fee=5,
            fixed=0,
            discount=0,
        )

        self.assertEqual(to_number('R$ 1.234,56'), 1234.56)
        self.assertEqual(calculate_price(100, margin=20, tax=10, fee=5), 153.85)
        self.assertIn('Preço unitário (OBRIGATÓRIO)', precificado.columns)
        self.assertEqual(float(precificado.loc[0, 'Preço unitário (OBRIGATÓRIO)']), 153.85)

    def test_estoque_por_planilha_exige_modelo_real_e_preenche_deposito(self) -> None:
        origem = pd.DataFrame({'sku': ['ABC-1'], 'saldo': ['7']})
        modelo = pd.DataFrame(columns=['Código', 'Depósito (OBRIGATÓRIO)', 'Balanço (OBRIGATÓRIO)'])

        final, mapping = run_estoque_engine(origem, modelo, deposito='Loja Principal')

        self.assertEqual(list(final.columns), list(modelo.columns))
        self.assertEqual(final.loc[0, 'Código'], 'ABC-1')
        self.assertEqual(final.loc[0, 'Depósito (OBRIGATÓRIO)'], 'Loja Principal')
        self.assertEqual(final.loc[0, 'Balanço (OBRIGATÓRIO)'], '7')
        self.assertEqual(mapping['Código'], 'sku')

        with self.assertRaises(MissingEstoqueModelError):
            run_estoque_engine(origem, None, deposito='Loja Principal')

    def test_site_estoque_so_usa_colunas_do_modelo_solicitado(self) -> None:
        modelo_estoque = pd.DataFrame(columns=['Código', 'Balanço (OBRIGATÓRIO)'])
        modelo_cadastro = pd.DataFrame(columns=['Descrição', 'Preço de venda', 'URL Imagens'])

        requested = requested_columns_for_site_capture('estoque', modelo_cadastro, modelo_estoque)

        self.assertEqual(requested, ['Código', 'Balanço (OBRIGATÓRIO)'])
        self.assertNotIn('Descrição', requested or [])
        self.assertNotIn('Preço de venda', requested or [])

    def test_site_cadastro_nao_mistura_colunas_de_estoque(self) -> None:
        modelo_estoque = pd.DataFrame(columns=['Código', 'Balanço (OBRIGATÓRIO)'])
        modelo_cadastro = pd.DataFrame(columns=['Descrição', 'Preço de venda', 'URL Imagens'])

        requested = requested_columns_for_site_capture('cadastro', modelo_cadastro, modelo_estoque)

        self.assertEqual(requested, ['Descrição', 'Preço de venda', 'URL Imagens'])
        self.assertNotIn('Balanço (OBRIGATÓRIO)', requested or [])

    def test_site_scraper_url_only_respeita_colunas_solicitadas_sem_http(self) -> None:
        df = run_fast_site_scraper(
            raw_urls='https://fornecedor.com/produto-1\nhttps://fornecedor.com/produto-2',
            requested_columns=['URL'],
            operation='estoque',
            max_pages=2,
            max_products=2,
        )

        self.assertEqual(list(df.columns), ['URL'])
        self.assertEqual(len(df), 2)
        self.assertTrue(df['URL'].str.startswith('https://').all())

    def test_exportador_limpa_gtin_invalido_e_preserva_separador_de_imagens(self) -> None:
        df = pd.DataFrame(
            {
                'GTIN/EAN': ['ABC123', '1234567890123'],
                'URL Imagens': [
                    'https://site.com/a.jpg; https://site.com/b.webp',
                    'https://site.com/c.png|https://site.com/c.png',
                ],
            }
        )

        safe = sanitize_for_bling(df)

        self.assertEqual(safe.loc[0, 'GTIN/EAN'], '')
        self.assertEqual(safe.loc[1, 'GTIN/EAN'], '1234567890123')
        self.assertEqual(safe.loc[0, 'URL Imagens'], 'https://site.com/a.jpg|https://site.com/b.webp')
        self.assertEqual(safe.loc[1, 'URL Imagens'], 'https://site.com/c.png')


if __name__ == '__main__':
    unittest.main()
