from __future__ import annotations

import unittest

import pandas as pd

from bling_app_zero.core.mobile_protected_capture import (
    MobileCaptureResult,
    _blocked_message,
    _frame_from_remote_payload,
    _looks_like_login_html,
    _merge_frames,
    _start_url_variants,
)


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

    def test_blocked_message_is_friendly_and_fallback_ready(self) -> None:
        message = _blocked_message('https://www.atacadum.com.br/', 401)
        self.assertIn('bloqueou a captura direta', message)
        self.assertIn('busca pública inteligente', message)
        result = MobileCaptureResult('blocked_direct_capture', message, details={'status_code': 401})
        self.assertTrue(result.should_try_public_engine)

    def test_start_url_variants_try_www_and_root(self) -> None:
        variants = _start_url_variants('https://www.atacadum.com.br')
        self.assertIn('https://www.atacadum.com.br', variants)
        self.assertIn('https://atacadum.com.br', variants)


if __name__ == '__main__':
    unittest.main()
