from __future__ import annotations

import unittest

from bling_app_zero.agents.site_platform_detector import detect_site_platform
from bling_app_zero.engines.fast_site_scraper.url_discovery import split_urls


class TestWBuyCurlUrls(unittest.TestCase):
    def test_split_urls_aproveita_referers_de_curl_e_ignora_action_css(self) -> None:
        raw = """
        curl 'https://www.atacadum.com.br/action.php' \
          -H 'referer: https://www.atacadum.com.br/relogio-smartwatch/' \
          --data-raw 'funcao=userdata' ;
        curl 'https://www.atacadum.com.br/action.php' \
          -H 'referer: https://www.atacadum.com.br/smartwatch-d20-atualizacao-2021/' \
          --data-raw 'funcao=cart-number' ;
        curl 'https://cdn.sistemawbuy.com.br/css/produtos_categorias.css?t=1782626384' \
          -H 'referer: https://www.atacadum.com.br/' ;
        """

        urls = split_urls(raw)

        self.assertIn('https://www.atacadum.com.br/relogio-smartwatch', urls)
        self.assertIn('https://www.atacadum.com.br/smartwatch-d20-atualizacao-2021', urls)
        self.assertIn('https://www.atacadum.com.br', urls)
        self.assertFalse(any('action.php' in url for url in urls))
        self.assertFalse(any('sistemawbuy.com.br' in url for url in urls))
        self.assertFalse(any('produtos_categorias.css' in url for url in urls))

    def test_detector_reconhece_wbuy_por_cdn_css_e_cookies(self) -> None:
        raw = """
        curl 'https://cdn.sistemawbuy.com.br/css/produtos_categorias.css?t=1782626384'
          -b 'wbuy_vid=a57c819f7bec1af90c835ee36687dbf8; wbhash=6a42c82f71420'
          -H 'referer: https://www.atacadum.com.br/'
        """

        signal = detect_site_platform(raw)

        self.assertEqual(signal.platform, 'wbuy')
        self.assertGreaterEqual(signal.confidence, 0.90)


if __name__ == '__main__':
    unittest.main()
