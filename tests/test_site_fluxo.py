from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from bling_app_zero.engines.fast_site_scraper.engine import run_fast_site_scraper
from bling_app_zero.engines.site_operations import run_site_operation_engine
from bling_app_zero.ui.site_models import requested_columns_for_site_capture


class TestSiteFluxo(unittest.TestCase):
    def test_site_estoque_usa_apenas_modelo_de_estoque(self) -> None:
        modelo_cadastro = pd.DataFrame(columns=['Descrição', 'Preço de venda', 'GTIN/EAN', 'URL Imagens'])
        modelo_estoque = pd.DataFrame(columns=['Código', 'Balanço (OBRIGATÓRIO)'])

        requested = requested_columns_for_site_capture('estoque', modelo_cadastro, modelo_estoque)

        self.assertEqual(requested, ['Código', 'Balanço (OBRIGATÓRIO)'])
        self.assertNotIn('Descrição', requested or [])
        self.assertNotIn('Preço de venda', requested or [])
        self.assertNotIn('URL Imagens', requested or [])

    def test_site_cadastro_usa_apenas_modelo_de_cadastro(self) -> None:
        modelo_cadastro = pd.DataFrame(columns=['Descrição', 'Preço de venda', 'GTIN/EAN', 'URL Imagens'])
        modelo_estoque = pd.DataFrame(columns=['Código', 'Balanço (OBRIGATÓRIO)'])

        requested = requested_columns_for_site_capture('cadastro', modelo_cadastro, modelo_estoque)

        self.assertEqual(requested, ['Descrição', 'Preço de venda', 'GTIN/EAN', 'URL Imagens'])
        self.assertNotIn('Balanço (OBRIGATÓRIO)', requested or [])

    def test_site_sem_modelo_estoque_nao_devolve_colunas_solicitadas(self) -> None:
        modelo_cadastro = pd.DataFrame(columns=['Descrição', 'Preço de venda'])

        requested = requested_columns_for_site_capture('estoque', modelo_cadastro, None)

        self.assertIsNone(requested)

    def test_site_scraper_url_only_nao_faz_http_e_respeita_contrato(self) -> None:
        df = run_fast_site_scraper(
            raw_urls='https://fornecedor.com/p/1\nhttps://fornecedor.com/p/2',
            requested_columns=['URL'],
            operation='cadastro',
            max_pages=2,
            max_products=2,
        )

        self.assertEqual(list(df.columns), ['URL'])
        self.assertEqual(len(df), 2)
        self.assertEqual(df.loc[0, 'URL'], 'https://fornecedor.com/p/1')
        self.assertEqual(df.loc[1, 'URL'], 'https://fornecedor.com/p/2')

    def test_motor_cadastro_independente_respeita_contrato_de_cadastro(self) -> None:
        with patch('bling_app_zero.engines.fast_site_scraper.engine.fetch_live', return_value=''):
            df = run_site_operation_engine(
                operation='cadastro',
                raw_urls='https://fornecedor.com/p/1',
                requested_columns=['URL', 'Descrição', 'Preço unitário (OBRIGATÓRIO)', 'URL Imagens'],
                max_pages=1,
                max_products=1,
            )

        self.assertEqual(list(df.columns), ['URL', 'Descrição', 'Preço unitário (OBRIGATÓRIO)', 'URL Imagens'])
        self.assertEqual(df.loc[0, 'URL'], 'https://fornecedor.com/p/1')

    def test_motor_estoque_sem_contrato_nao_cai_no_cadastro(self) -> None:
        df = run_site_operation_engine(
            operation='estoque',
            raw_urls='https://fornecedor.com/p/1',
            requested_columns=None,
            max_pages=1,
            max_products=1,
        )

        self.assertEqual(list(df.columns), [])
        self.assertEqual(len(df), 0)

    def test_motores_deduplicam_colunas_do_contrato(self) -> None:
        cadastro = run_site_operation_engine(
            operation='cadastro',
            raw_urls='https://fornecedor.com/p/1',
            requested_columns=['URL', 'URL', 'Descrição', 'Descrição'],
            max_pages=1,
            max_products=1,
        )
        estoque = run_site_operation_engine(
            operation='estoque',
            raw_urls='https://fornecedor.com/p/1',
            requested_columns=['Código', 'Código', 'Balanço (OBRIGATÓRIO)', 'Balanço (OBRIGATÓRIO)'],
            max_pages=1,
            max_products=1,
        )

        self.assertEqual(list(cadastro.columns), ['URL', 'Descrição'])
        self.assertEqual(list(estoque.columns), ['Código', 'Balanço (OBRIGATÓRIO)'])


if __name__ == '__main__':
    unittest.main()
