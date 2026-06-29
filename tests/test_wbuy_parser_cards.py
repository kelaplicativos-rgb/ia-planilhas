from __future__ import annotations

import unittest

from bling_app_zero.engines.fast_site_scraper.wbuy_parser import wbuy_listing_products, wbuy_product_links


WBUY_CATEGORY_HTML = """
<!doctype html>
<html>
<head>
    <meta name="author" content="wBuy Lojas Virtuais - www.wbuy.com.br">
    <title>Comprar OFERTAS</title>
    <script>
        window.performaData = {};
        window.performaData.pageType = "category";
        window.performaData.categoryID = "261903";
    </script>
</head>
<body>
    <div id="slider" class="owl-carousel">
        <img src="https://cdn.sistemawbuy.com.br/arquivos/loja/slide/banner_mini.jpg" alt="Banner">
    </div>
    <nav aria-label="breadcrumb">
        <a><span itemprop="name">Página inicial</span></a>
        <a><span itemprop="name">OFERTAS</span></a>
    </nav>
    <div class="produtos">
        <div class="item" data-id="5273699" data-sku="5273699.64240.128656">
            <a href="https://www.atacadum.com.br/smartwatch-c11-ultra-49mm-serie-11-jogos-pulseira-extra-lancamento/">
                <div class="fotos">
                    <img data-src="https://cdn.sistemawbuy.com.br/arquivos/239/produtos/69c05d65c7d40/1-69c06011ae4fd_mini.jpg" src="./Comprar OFERTAS_files/1.jpg" alt="Smartwatch C11 Ultra 49mm Serie 11 Jogos Pulseira Extra Lançamento">
                    <img data-src="https://cdn.sistemawbuy.com.br/arquivos/239/produtos/69c05d65c7d40/5-69c05f772a428_mini.jpg" alt="Smartwatch C11 Ultra 49mm Serie 11 Jogos Pulseira Extra Lançamento">
                </div>
            </a>
            <h3 class="produto" title="Smartwatch C11 Ultra 49mm Serie 11 Jogos Pulseira Extra Lançamento" data-canbuy="1">Smartwatch C11 Ultra</h3>
            <div class="valor">
                <p class="valor_de"><span>de</span> <span class="vlr">R$160,00</span> <span>por</span></p>
                <p class="valor_final"><span>R$65,00</span></p>
            </div>
            <div class="cores">
                <span class="cor_primaria" title="Preto" style="background: url('https://cdn.sistemawbuy.com.br/arquivos/239/produtos/69c05d65c7d40/6-69c0601c0b028_mini.jpg') center center;"></span>
            </div>
            <div class="botoes">
                <a href="https://www.atacadum.com.br/#" class="b_olhar">Olhar</a>
                <a href="https://www.atacadum.com.br/smartwatch-c11-ultra-49mm-serie-11-jogos-pulseira-extra-lancamento/" class="b_acao">Comprar</a>
            </div>
        </div>
        <div class="item" data-id="3303464" data-sku="3303464.115531.127812">
            <a href="https://www.atacadum.com.br/smartwatch-ultra-ai-3-5g-2-16gb-com-chip/">
                <img data-src="https://cdn.sistemawbuy.com.br/arquivos/239/produtos/66c5e2e7e3ef0/24-66cdbd8daa6d7_mini.jpg" alt="Smartwatch Microwear Ultra 3 Ai 5G 2/16GB Amoled Com Chip Android Camera Wifi">
            </a>
            <h3 class="produto" title="Smartwatch Microwear Ultra 3 Ai 5G 2/16GB Amoled Com Chip Android Camera Wifi" data-canbuy="1">Smartwatch Microwear Ultra 3 Ai 5G 2/16GB Amoled Com Chip Android Camera Wifi</h3>
            <div class="valor"><p class="valor_de"><span class="vlr">R$380,00</span></p><p class="valor_final"><span>R$270,00</span></p></div>
            <a class="b_acao" href="https://www.atacadum.com.br/smartwatch-ultra-ai-3-5g-2-16gb-com-chip/">Comprar</a>
        </div>
    </div>
</body>
</html>
"""


class TestWBuyCategoryCardParser(unittest.TestCase):
    def test_extracts_real_wbuy_cards_and_ignores_slider(self) -> None:
        products = wbuy_listing_products('https://www.atacadum.com.br/ofertas/', WBUY_CATEGORY_HTML, limit=20)

        self.assertEqual(len(products), 2)
        self.assertEqual(products[0].id_produto, '5273699')
        self.assertEqual(products[0].codigo, '5273699.64240.128656')
        self.assertEqual(products[0].preco, '65,00')
        self.assertEqual(products[0].estoque, '10')
        self.assertEqual(products[0].categoria, 'OFERTAS')
        self.assertIn('Smartwatch C11 Ultra', products[0].descricao)
        self.assertIn('Preço anterior: 160,00', products[0].descricao_complementar)
        self.assertIn('|', products[0].imagem)
        self.assertIn('/produtos/69c05d65c7d40/', products[0].imagem)
        self.assertNotIn('/slide/', products[0].imagem)
        self.assertEqual(products[1].marca, 'Microwear')

    def test_product_links_prefer_card_purchase_urls(self) -> None:
        links = wbuy_product_links('https://www.atacadum.com.br/ofertas/', WBUY_CATEGORY_HTML, limit=10)

        self.assertEqual(len(links), 2)
        self.assertTrue(all('#' not in link for link in links))
        self.assertIn('smartwatch-c11-ultra-49mm', links[0])

    def test_action_php_user_cart_text_does_not_generate_products(self) -> None:
        text = "curl 'https://www.atacadum.com.br/action.php' --data-raw 'funcao=userdata'; --data-raw 'funcao=cart-number'"
        self.assertEqual(wbuy_listing_products('https://www.atacadum.com.br/ofertas/', text, limit=10), [])


if __name__ == '__main__':
    unittest.main()
