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


if __name__ == '__main__':
    unittest.main()
