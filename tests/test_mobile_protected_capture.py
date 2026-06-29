from __future__ import annotations

import unittest

import pandas as pd

from bling_app_zero.core.mobile_protected_capture import _frame_from_remote_payload, _looks_like_login_html, _merge_frames


class TestMobileProtectedCapture(unittest.TestCase):
    def test_detects_login_page(self) -> None:
        html = '<html><body><form><input name="email"><input type="password" name="senha"><button>Entrar</button></form></body></html>'
        self.assertTrue(_looks_like_login_html(html))

    def test_remote_rows_payload_to_frame(self) -> None:
        df = _frame_from_remote_payload({'rows': [{'SKU': 'ABC-1', 'Nome': 'Produto A', 'Estoque': '7'}]})
        self.assertEqual(len(df), 1)
        self.assertEqual(df.loc[0, 'SKU'], 'ABC-1')

    def test_merge_frames_dedupes_by_sku(self) -> None:
        first = pd.DataFrame([{'SKU': 'A1', 'Nome': 'Produto 1'}, {'SKU': 'A2', 'Nome': 'Produto 2'}])
        second = pd.DataFrame([{'SKU': 'A2', 'Nome': 'Produto 2 duplicado'}, {'SKU': 'A3', 'Nome': 'Produto 3'}])
        merged = _merge_frames([first, second])
        self.assertEqual(len(merged), 3)
        self.assertEqual(set(merged['SKU']), {'A1', 'A2', 'A3'})


if __name__ == '__main__':
    unittest.main()
