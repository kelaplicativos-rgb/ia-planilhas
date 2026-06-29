from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from bling_app_zero.engines.fast_site_scraper.engine import run_fast_site_scraper
from bling_app_zero.engines.site_operations import run_site_operation_engine
from bling_app_zero.engines.site_operations.submotors import build_submotor_plan
from bling_app_zero.pipelines.site_pipeline import _clean_site_description_columns, _infer_operation_from_columns
from bling_app_zero.ui.site_models import choose_site_cadastro_model_df, choose_site_estoque_model_df, requested_columns_for_site_capture


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

    def test_site_universal_junta_modelo_cadastro_e_estoque(self) -> None:
        modelo_cadastro = pd.DataFrame(columns=['Descrição', 'Preço de venda', 'GTIN/EAN', 'URL Imagens'])
        modelo_estoque = pd.DataFrame(columns=['Código', 'Descrição', 'Balanço (OBRIGATÓRIO)', 'Depósito (OBRIGATÓRIO)'])

        requested = requested_columns_for_site_capture('universal', modelo_cadastro, modelo_estoque)

        self.assertEqual(
            requested,
            ['Descrição', 'Preço de venda', 'GTIN/EAN', 'URL Imagens', 'Código', 'Balanço (OBRIGATÓRIO)', 'Depósito (OBRIGATÓRIO)'],
        )

    def test_site_sem_modelo_estoque_nao_devolve_colunas_solicitadas(self) -> None:
        modelo_cadastro = pd.DataFrame(columns=['Descrição', 'Preço de venda'])

        requested = requested_columns_for_site_capture('estoque', modelo_cadastro, None)

        self.assertIsNone(requested)

    def test_site_ignora_model_df_generico_para_nao_misturar_operacoes(self) -> None:
        modelo_generico_cadastro = pd.DataFrame(columns=['Descrição', 'Preço de venda', 'URL Imagens'])
        modelo_generico_estoque = pd.DataFrame(columns=['Código', 'Balanço (OBRIGATÓRIO)'])
        upload_cadastro_errado = SimpleNamespace(
            cadastro_model_df=None,
            estoque_model_df=None,
            model_df=modelo_generico_cadastro,
        )
        upload_estoque_errado = SimpleNamespace(
            cadastro_model_df=None,
            estoque_model_df=None,
            model_df=modelo_generico_estoque,
        )

        with patch('bling_app_zero.ui.site_models.get_home_estoque_model', return_value=None):
            self.assertIsNone(choose_site_estoque_model_df(upload_cadastro_errado))
        with patch('bling_app_zero.ui.site_models.get_home_cadastro_model', return_value=None):
            self.assertIsNone(choose_site_cadastro_model_df(upload_estoque_errado))

    def test_site_usa_modelo_correto_classificado_no_upload(self) -> None:
        modelo_cadastro = pd.DataFrame(columns=['Descrição', 'Preço de venda'])
        modelo_estoque = pd.DataFrame(columns=['Código', 'Balanço (OBRIGATÓRIO)'])
        upload = SimpleNamespace(
            cadastro_model_df=modelo_cadastro,
            estoque_model_df=modelo_estoque,
            model_df=None,
        )

        self.assertEqual(list(choose_site_cadastro_model_df(upload).columns), ['Descrição', 'Preço de venda'])
        self.assertEqual(list(choose_site_estoque_model_df(upload).columns), ['Código', 'Balanço (OBRIGATÓRIO)'])

    def test_site_estoque_preserva_ordem_exata_do_modelo_anexado(self) -> None:
        modelo_estoque = pd.DataFrame(
            columns=[
                'ID Produto',
                'Código',
                'Descrição',
                'Depósito (OBRIGATÓRIO)',
                'Balanço (OBRIGATÓRIO)',
                'Observações',
            ]
        )

        requested = requested_columns_for_site_capture('estoque', None, modelo_estoque)

        self.assertEqual(
            requested,
            [
                'ID Produto',
                'Código',
                'Descrição',
                'Depósito (OBRIGATÓRIO)',
                'Balanço (OBRIGATÓRIO)',
                'Observações',
            ],
        )

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

    def test_motor_universal_respeita_contrato_unico(self) -> None:
        with patch('bling_app_zero.engines.fast_site_scraper.engine.fetch_live', return_value=''):
            df = run_site_operation_engine(
                operation='universal',
                raw_urls='https://fornecedor.com/p/1',
                requested_columns=['URL', 'Descrição', 'Preço unitário (OBRIGATÓRIO)', 'Balanço (OBRIGATÓRIO)'],
                max_pages=1,
                max_products=1,
            )

        self.assertEqual(list(df.columns), ['URL', 'Descrição', 'Preço unitário (OBRIGATÓRIO)', 'Balanço (OBRIGATÓRIO)'])
        self.assertEqual(df.loc[0, 'URL'], 'https://fornecedor.com/p/1')

    def test_site_pipeline_modelo_universal_misto_nao_vira_estoque(self) -> None:
        columns = [
            'URL',
            'ID Produto',
            'Código SKU*',
            'GTIN/EAN**',
            'Nome do Produto',
            'Depósito*',
            'Movimentação de Estoque*',
            'Tipo de lançamento*',
            'Preço de Compra*',
            'Preço de Custo',
            'Observação',
        ]

        selected = _infer_operation_from_columns('universal', columns)

        self.assertEqual(selected, 'universal')

    def test_site_pipeline_modelo_universal_estoque_puro_ainda_usa_estoque(self) -> None:
        columns = ['Código SKU*', 'Depósito*', 'Movimentação de Estoque*']

        selected = _infer_operation_from_columns('universal', columns)

        self.assertEqual(selected, 'estoque')

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
        with patch('bling_app_zero.engines.fast_site_scraper.engine.fetch_live', return_value=''):
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
            universal = run_site_operation_engine(
                operation='universal',
                raw_urls='https://fornecedor.com/p/1',
                requested_columns=['URL', 'URL', 'Descrição', 'Descrição', 'Balanço (OBRIGATÓRIO)'],
                max_pages=1,
                max_products=1,
            )

        self.assertEqual(list(cadastro.columns), ['URL', 'Descrição'])
        self.assertEqual(list(estoque.columns), ['Código', 'Balanço (OBRIGATÓRIO)'])
        self.assertEqual(list(universal.columns), ['URL', 'Descrição', 'Balanço (OBRIGATÓRIO)'])

    def test_site_pipeline_limpa_descricao_suja_de_qualquer_motor(self) -> None:
        df = pd.DataFrame([
            {
                'Descrição': 'Teclado USB AL-507',
                'Descrição complementar': (
                    'Descrição Teclado USB AL-507, perfeito para escritório ou home office. '
                    'Conexão USB plug-and-play sem instalação de drivers. '
                    'Ainda não há para este produto Teclado USB AL-507'
                ),
            }
        ])

        cleaned = _clean_site_description_columns(df, 'cadastro')
        value = cleaned.loc[0, 'Descrição complementar']

        self.assertIn('Teclado USB AL-507, perfeito para escritório ou home office', value)
        self.assertIn('Conexão USB plug-and-play sem instalação de drivers', value)
        self.assertNotIn('Descrição Teclado', value)
        self.assertNotIn('Ainda não há', value)
        self.assertFalse(value.endswith('Teclado USB AL-507'))

    def test_site_pipeline_limpa_coluna_descricao_simples_quando_vem_suja(self) -> None:
        df = pd.DataFrame([
            {
                'Descrição': (
                    'Descrição Teclado USB AL-507, perfeito para escritório ou home office. '
                    'Conexão USB plug-and-play sem instalação de drivers, compatível com Windows, macOS e notebooks. '
                    'Layout completo com teclado numérico, tecla Windows dedicada e atalhos úteis para acelerar tarefas diárias. '
                    'Digitação estável, resposta tátil agradável e construção durável para uso contínuo em qualquer estação de trabalho. '
                    'Ainda não há para este produto Teclado USB AL-507'
                ),
            }
        ])

        cleaned = _clean_site_description_columns(df, 'cadastro')
        value = cleaned.loc[0, 'Descrição']

        self.assertIn('Teclado USB AL-507, perfeito para escritório ou home office', value)
        self.assertIn('Conexão USB plug-and-play sem instalação de drivers', value)
        self.assertIn('Layout completo com teclado numérico', value)
        self.assertNotIn('Descrição Teclado', value)
        self.assertNotIn('Ainda não há', value)
        self.assertFalse(value.endswith('Teclado USB AL-507'))

    def test_site_pipeline_preserva_descricao_curta_legitima(self) -> None:
        df = pd.DataFrame([{'Descrição': 'Teclado USB AL-507'}])

        cleaned = _clean_site_description_columns(df, 'cadastro')

        self.assertEqual(cleaned.loc[0, 'Descrição'], 'Teclado USB AL-507')

    def test_plano_de_submotores_muda_por_operacao(self) -> None:
        cadastro_plan = build_submotor_plan(
            'cadastro',
            ['URL', 'Descrição', 'Preço unitário (OBRIGATÓRIO)', 'URL Imagens', 'Categoria'],
        )
        estoque_plan = build_submotor_plan(
            'estoque',
            ['Código', 'Balanço (OBRIGATÓRIO)'],
        )
        universal_plan = build_submotor_plan(
            'universal',
            ['URL', 'Descrição', 'Preço unitário (OBRIGATÓRIO)', 'URL Imagens', 'Balanço (OBRIGATÓRIO)'],
        )

        self.assertEqual(cadastro_plan.operation, 'cadastro')
        self.assertIn('preco', cadastro_plan.active)
        self.assertIn('imagens', cadastro_plan.active)
        self.assertIn('categoria', cadastro_plan.active)
        self.assertEqual(estoque_plan.operation, 'estoque')
        self.assertIn('identificacao', estoque_plan.active)
        self.assertIn('estoque', estoque_plan.active)
        self.assertNotIn('imagens', estoque_plan.active)
        self.assertEqual(universal_plan.operation, 'universal')
        self.assertIn('preco', universal_plan.active)
        self.assertIn('estoque', universal_plan.active)
        self.assertIn('imagens', universal_plan.active)


if __name__ == '__main__':
    unittest.main()