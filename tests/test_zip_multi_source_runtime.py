from __future__ import annotations

import unittest
import zipfile
from io import BytesIO

from bling_app_zero.core.zip_multi_source_runtime import install_zip_multi_source_runtime


HTML_PAGE_1 = '''
<html><body><table><thead><tr><th>SKU</th><th>Título</th><th>Estoque</th><th>Preço</th></tr></thead><tbody>
<tr><td>OOM-0001</td><td>Produto Um</td><td><span data-original-title="2 Unidades">Baixo</span></td><td>R$ 10,00</td></tr>
</tbody></table></body></html>
'''

HTML_PAGE_2 = '''
<html><body><table><thead><tr><th>SKU</th><th>Título</th><th>Estoque</th><th>Preço</th></tr></thead><tbody>
<tr><td>OOM-0002</td><td>Produto Dois</td><td><span data-original-title="50 Unidades">Disponível</span></td><td>R$ 20,00</td></tr>
</tbody></table></body></html>
'''

DETAILS_HTML = '''
<html><body><table><thead><tr><th>SKU</th><th>ID Produto</th><th>GTIN</th><th>GTIN/EAN**</th></tr></thead><tbody>
<tr><td>OOM-0001</td><td>10</td><td>7891234567895</td><td>7891234567895</td></tr>
</tbody></table></body></html>
'''

MODEL_CSV = 'ID Produto,Código SKU*,GTIN/EAN**,Nome do Produto,Depósito*,Movimentação de Estoque*,Tipo de lançamento*,Preço de Compra*,Preço de Custo,Observação\nLinha de exemplo,FL458,1234567891023,Bolsa pequena,Depósito Geral,250,Entrada,760,850,\n'


class TestZipMultiSourceRuntime(unittest.TestCase):
    def test_zip_with_multiple_html_pages_is_concatenated(self) -> None:
        install_zip_multi_source_runtime()
        from bling_app_zero.core import files as files_module

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('pagina_001.html', HTML_PAGE_1)
            zf.writestr('pagina_002.html', HTML_PAGE_2)
        df = files_module._read_zip_bytes(buffer.getvalue(), 'capturas.zip')

        self.assertEqual(len(df), 2)
        self.assertEqual(set(df['SKU']), {'OOM-0001', 'OOM-0002'})
        self.assertEqual(df.loc[df['SKU'] == 'OOM-0001', 'Balanço (OBRIGATÓRIO)'].iloc[0], '2')
        self.assertEqual(df.loc[df['SKU'] == 'OOM-0002', 'Balanço (OBRIGATÓRIO)'].iloc[0], '50')
        self.assertIn('Arquivo origem', df.columns)
        self.assertIn('Página origem', df.columns)

    def test_zip_with_detail_html_fills_gtin_on_existing_sku(self) -> None:
        install_zip_multi_source_runtime()
        from bling_app_zero.core import files as files_module

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('pagina_001.html', HTML_PAGE_1)
            zf.writestr('detalhes_001.html', DETAILS_HTML)
        df = files_module._read_zip_bytes(buffer.getvalue(), 'capturas_com_detalhes.zip')

        self.assertEqual(len(df), 1)
        self.assertEqual(df.loc[0, 'SKU'], 'OOM-0001')
        self.assertEqual(df.loc[0, 'GTIN'], '7891234567895')
        self.assertEqual(df.loc[0, 'GTIN **'], '7891234567895')

    def test_zip_with_same_model_in_multiple_files_does_not_generate_columns(self) -> None:
        install_zip_multi_source_runtime()
        from bling_app_zero.core import files as files_module

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('saldo_estoque.csv', MODEL_CSV.encode('utf-8-sig'))
            zf.writestr('saldo_estoque_backup.csv', MODEL_CSV.encode('utf-8-sig'))
        df = files_module._read_zip_bytes(buffer.getvalue(), 'saldo_estoque.csv.zip')

        self.assertEqual(list(df.columns), ['ID Produto', 'Código SKU*', 'GTIN/EAN**', 'Nome do Produto', 'Depósito*', 'Movimentação de Estoque*', 'Tipo de lançamento*', 'Preço de Compra*', 'Preço de Custo', 'Observação'])
        self.assertNotIn('Arquivo origem', df.columns)
        self.assertNotIn('Página origem', df.columns)
        self.assertEqual(len(df), 1)


if __name__ == '__main__':
    unittest.main()
