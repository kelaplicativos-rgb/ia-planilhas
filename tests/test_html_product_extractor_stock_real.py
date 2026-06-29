from __future__ import annotations

import unittest

from bling_app_zero.core.html_product_extractor import read_html_product_text


OBA_TABLE_HTML = '''
<html><body>
<table class="datatable datatable-Product" id="DataTables_Table_0">
<thead><tr>
<th>SKU</th><th>Foto</th><th>Título</th><th>Modelo</th><th>Marca</th><th>Preço</th><th>Estoque</th><th>Ações</th>
</tr></thead>
<tbody>
<tr>
<td><span>OOM-0550</span></td>
<td><a href="https://media.obaobamix.com.br/790504/6801337a663d8.jpg" title="&lt;img src='https://media.obaobamix.com.br/790504/6801337a663d8.jpg' /&gt;"><img src="preview.jpg"></a></td>
<td><div class="small">Rosa-neon</div>Copo Térmico com Tampa e Abridor 591ml [Rosa Neon]<span data-original-title="Queima de Estoque">QE</span></td>
<td>OT-RN591</td>
<td>Oba Térmic</td>
<td><div>R$ 70,90</div><span>R$</span> 29,90</td>
<td><span class="badge bg-warning" data-original-title="2 Unidades">Baixo</span></td>
<td><a id="btnViewProduct" data-id="550">Visualizar</a></td>
</tr>
<tr>
<td>OOM-0549</td>
<td><a href="https://media.obaobamix.com.br/792236/6807f9e723657.jpg"><img src="preview2.jpg"></a></td>
<td>Produto Disponível</td>
<td>OT-VM591</td>
<td>Oba Térmic</td>
<td>R$ 29,90</td>
<td><span class="badge bg-success" data-original-title="50 Unidades">Disponível</span></td>
<td><a id="btnViewProduct" data-id="549">Visualizar</a></td>
</tr>
<tr>
<td>OOM-0520</td>
<td><img src="https://media.obaobamix.com.br/135233/produto.jpg"></td>
<td>Mini Processador de Alimentos</td>
<td>CK5422</td>
<td>Clink</td>
<td>R$ 19,90</td>
<td><span class="badge bg-danger" data-original-title="Sem Previsão">Esgotado</span></td>
<td><a id="btnViewProduct" data-id="520">Visualizar</a></td>
</tr>
</tbody>
</table>
</body></html>
'''


class TestHtmlProductExtractorStockReal(unittest.TestCase):
    def test_oba_tooltip_stock_becomes_numeric_balance(self) -> None:
        df = read_html_product_text(OBA_TABLE_HTML)

        self.assertEqual(len(df), 3)
        self.assertEqual(df.loc[0, 'Código produto'], 'OOM-0550')
        self.assertEqual(df.loc[0, 'ID Produto'], '550')
        self.assertEqual(df.loc[0, 'Balanço (OBRIGATÓRIO)'], '2')
        self.assertEqual(df.loc[0, 'Estoque'], '2')
        self.assertEqual(df.loc[0, 'Quantidade extraída do estoque'], '2')
        self.assertIn('Baixo', df.loc[0, 'Status Estoque'])
        self.assertIn('https://media.obaobamix.com.br/790504/6801337a663d8.jpg', df.loc[0, 'Imagem'])
        self.assertEqual(df.loc[1, 'Balanço (OBRIGATÓRIO)'], '50')
        self.assertEqual(df.loc[2, 'Balanço (OBRIGATÓRIO)'], '0')


if __name__ == '__main__':
    unittest.main()
