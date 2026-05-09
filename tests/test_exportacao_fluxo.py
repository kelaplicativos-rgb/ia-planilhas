from __future__ import annotations

import unittest

import pandas as pd

from bling_app_zero.core.exporter import filename_for_operation, sanitize_for_bling, to_bling_csv_bytes


class TestExportacaoFluxo(unittest.TestCase):
    def test_exportacao_csv_usa_ponto_e_virgula_utf8_sig(self) -> None:
        df = pd.DataFrame({'Código': ['P001'], 'Descrição': ['Produto Teste']})

        csv_bytes = to_bling_csv_bytes(df)
        csv_text = csv_bytes.decode('utf-8-sig')

        self.assertTrue(csv_bytes.startswith(b'\xef\xbb\xbf'))
        self.assertIn('Código;Descrição', csv_text)
        self.assertIn('P001;Produto Teste', csv_text)

    def test_exportacao_limpa_gtin_invalido(self) -> None:
        df = pd.DataFrame({'GTIN/EAN': ['ABC123', '12345678', '1234567890123', '123456789012345']})

        safe = sanitize_for_bling(df)

        self.assertEqual(safe['GTIN/EAN'].tolist(), ['', '12345678', '1234567890123', ''])

    def test_exportacao_imagens_usa_pipe_remove_duplicadas_e_ignora_invalidas(self) -> None:
        df = pd.DataFrame(
            {
                'URL Imagens': [
                    'https://site.com/a.jpg, https://site.com/b.webp; arquivo-local.png; https://site.com/a.jpg'
                ]
            }
        )

        safe = sanitize_for_bling(df)

        self.assertEqual(safe.loc[0, 'URL Imagens'], 'https://site.com/a.jpg|https://site.com/b.webp')

    def test_filename_por_operacao(self) -> None:
        self.assertEqual(filename_for_operation('cadastro'), 'bling_cadastro_produtos.csv')
        self.assertEqual(filename_for_operation('estoque'), 'bling_atualizacao_estoque.csv')
        self.assertEqual(filename_for_operation('outro'), 'bling_exportacao.csv')


if __name__ == '__main__':
    unittest.main()
