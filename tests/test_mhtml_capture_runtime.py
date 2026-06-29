from __future__ import annotations

import unittest

from bling_app_zero.core.mhtml_capture_runtime import install_mhtml_capture_runtime


MHTML_WITH_DOUBLE_CR = b'''From: <Saved by Blink>\r\r\nMIME-Version: 1.0\r\r\nContent-Type: multipart/related; boundary="----mapeiaai"\r\r\n\r\r\n------mapeiaai\r\r\nContent-Type: text/html; charset=UTF-8\r\r\nContent-Transfer-Encoding: quoted-printable\r\r\n\r\r\n<html><body><table><tr><th>SKU</th><th>T\xc3\xadtulo</th><th>Estoque</th></tr><tr><td>OOM-1</td><td>Produto Teste</td><td><span data-original-title=3D"7 Unidades">Disponivel</span></td></tr></table></body></html>\r\r\n------mapeiaai--\r\r\n'''


class TestMhtmlCaptureRuntime(unittest.TestCase):
    def test_reads_blink_mhtml_with_double_crlf_and_tooltip_stock(self) -> None:
        install_mhtml_capture_runtime()
        from bling_app_zero.core import html_product_extractor as hpe

        df = hpe.read_mhtml_product_bytes(MHTML_WITH_DOUBLE_CR)

        self.assertEqual(len(df), 1)
        self.assertEqual(df.loc[0, 'SKU'], 'OOM-1')
        self.assertEqual(df.loc[0, 'Balanço (OBRIGATÓRIO)'], '7')
        self.assertEqual(df.loc[0, 'Quantidade extraída do estoque'], '7')


if __name__ == '__main__':
    unittest.main()
