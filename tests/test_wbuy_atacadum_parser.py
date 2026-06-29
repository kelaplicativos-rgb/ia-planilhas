from __future__ import annotations

from bling_app_zero.engines.fast_site_scraper.wbuy_parser import wbuy_listing_products, wbuy_product_links


ATACADUM_CATEGORY_HTML = '''
<html>
<head>
    <title>Comprar Celulares Smartphone</title>
    <script src="https://cdn.sistemawbuy.com.br/cdn/jquery/jquery-3.7.1.min.js"></script>
</head>
<body>
    <div class="owl-carousel slider">
        <picture><img src="https://cdn.sistemawbuy.com.br/arquivos/loja/slide/content.jpg" alt="Grupos"></picture>
    </div>
    <div class="produtos">
        <div class="item" data-id="12345" data-sku="SKU-12345">
            <a href="/smartwatch-howear-hw-ultra-3-49mm-amoled-gps/">
                <img data-src="https://cdn.sistemawbuy.com.br/arquivos/loja/produtos/12345/1_mini.jpg" alt="Smartwatch Howear Hw Ultra 3 49mm Amoled Gps">
            </a>
            <h3 class="produto" title="Smartwatch Howear Hw Ultra 3 49mm Amoled Gps">Smartwatch Howear Hw Ultra 3 49mm Amoled Gps</h3>
            <div class="valor_de"><span>R$299,00</span></div>
            <div class="valor_final"><span>R$250,00</span></div>
        </div>
        <div class="item" data-id="67890" data-sku="SKU-67890">
            <a class="b_acao" href="/fone-bluetooth-xiaomi-airdots-original/">
                <img src="https://cdn.sistemawbuy.com.br/arquivos/loja/produtos/67890/1_mini.jpg" alt="Fone Bluetooth Xiaomi Airdots Original">
            </a>
            <h3 class="produto">Fone Bluetooth Xiaomi Airdots Original</h3>
            <div class="valor_final"><span>R$89,90</span></div>
        </div>
    </div>
    <a href="/action.php">carrinho</a>
    <a href="/global.php">global</a>
    <a href="/loadcomponents">componentes</a>
</body>
</html>
'''


def test_atacadum_wbuy_category_cards_extract_name_price_sku_url_and_image() -> None:
    products = wbuy_listing_products('https://www.atacadum.com.br/celulares-smartphone/', ATACADUM_CATEGORY_HTML, limit=10)

    assert len(products) == 2
    assert products[0].codigo == 'SKU-12345'
    assert products[0].descricao == 'Smartwatch Howear Hw Ultra 3 49mm Amoled Gps'
    assert products[0].preco == '250,00'
    assert products[0].url == 'https://www.atacadum.com.br/smartwatch-howear-hw-ultra-3-49mm-amoled-gps'
    assert '/produtos/12345/' in products[0].imagem
    assert products[0].categoria == 'Celulares Smartphone'


def test_atacadum_wbuy_links_ignore_jquery_technical_endpoints_and_slides() -> None:
    links = wbuy_product_links('https://www.atacadum.com.br/celulares-smartphone/', ATACADUM_CATEGORY_HTML, limit=10)

    assert links == [
        'https://www.atacadum.com.br/smartwatch-howear-hw-ultra-3-49mm-amoled-gps',
        'https://www.atacadum.com.br/fone-bluetooth-xiaomi-airdots-original',
    ]
    assert not any('action.php' in link or 'global.php' in link or 'loadcomponents' in link for link in links)
