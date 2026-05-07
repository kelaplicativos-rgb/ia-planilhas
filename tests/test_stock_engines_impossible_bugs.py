from __future__ import annotations

from bling_app_zero.core.site_engines.stock_feed_engine import _match_row, _quantity_from_row, _rows_from_feed
from bling_app_zero.core.site_engines.stock_value_engine import extract_real_stock_value, normalize_quantity

PRODUCT_URL = "https://megacentereletronicos.com.br/produto/controle-gamer-usb-kap-2u"


def test_stock_value_empty_html_returns_not_found() -> None:
    result = extract_real_stock_value("", page_url=PRODUCT_URL)
    assert result.quantity == ""
    assert result.source == "nao_encontrado"
    assert result.confidence == "nenhuma"


def test_stock_value_out_of_stock_overrides_buy_button() -> None:
    html = "<button>Comprar</button><p>Produto indisponível. Sem estoque.</p>"
    result = extract_real_stock_value(html, page_url=PRODUCT_URL)
    assert result.quantity == "0"
    assert result.source == "texto_indisponivel"
    assert result.confidence == "alta"


def test_stock_value_decimal_and_comma_quantity_normalizes() -> None:
    assert normalize_quantity("12,00 unidades") == "12"
    assert normalize_quantity("7.50") == "7.5"


def test_stock_value_json_nested_available_quantity() -> None:
    html = '<script type="application/json">{"product":{"inventory":{"availableQuantity":31}}}</script>'
    result = extract_real_stock_value(html, page_url=PRODUCT_URL)
    assert result.quantity == "31"
    assert result.source == "json"
    assert result.confidence == "alta"


def test_stock_value_html_attr_beats_visible_available_fallback() -> None:
    html = '<div data-stock="22"></div><button>Comprar</button>'
    result = extract_real_stock_value(html, page_url=PRODUCT_URL)
    assert result.quantity == "22"
    assert result.source == "html_attrs"
    assert result.confidence == "alta"


def test_stock_value_script_stock_quantity() -> None:
    html = '<script>window.PRODUCT = { sku: "KAP2U", stock_quantity: 44 };</script>'
    result = extract_real_stock_value(html, page_url=PRODUCT_URL)
    assert result.quantity == "44"
    assert result.source == "scripts"
    assert result.confidence == "alta"


def test_stock_feed_xml_google_namespace_quantity() -> None:
    feed = """
    <rss xmlns:g="http://base.google.com/ns/1.0">
      <channel>
        <item>
          <g:id>KAP2U</g:id>
          <g:title>Controle Gamer USB Kap-2U</g:title>
          <g:link>https://megacentereletronicos.com.br/produto/controle-gamer-usb-kap-2u</g:link>
          <g:availability>in_stock</g:availability>
          <g:quantity>18</g:quantity>
        </item>
      </channel>
    </rss>
    """
    rows = _rows_from_feed(feed)
    assert rows
    row = rows[0]
    assert _match_row(row, page_url=PRODUCT_URL, sku="KAP2U")
    qty, source = _quantity_from_row(row)
    assert qty == "18"
    assert source in {"quantity", "g:quantity"}


def test_stock_feed_availability_out_of_stock_returns_zero() -> None:
    feed = """
    <rss>
      <channel>
        <item>
          <id>KAP2U</id>
          <link>https://megacentereletronicos.com.br/produto/controle-gamer-usb-kap-2u</link>
          <availability>out_of_stock</availability>
        </item>
      </channel>
    </rss>
    """
    rows = _rows_from_feed(feed)
    qty, source = _quantity_from_row(rows[0])
    assert qty == "0"
    assert source == "availability"


def test_stock_feed_json_products_nested_stock() -> None:
    feed = '{"products":[{"sku":"KAP2U","link":"https://megacentereletronicos.com.br/produto/controle-gamer-usb-kap-2u","inventory":{"stockQuantity":27}}]}'
    rows = _rows_from_feed(feed)
    assert rows
    assert _match_row(rows[0], page_url=PRODUCT_URL, sku="KAP2U")
    qty, source = _quantity_from_row(rows[0])
    assert qty == "27"
    assert "stockquantity" in source.lower()


def test_stock_feed_broken_xml_does_not_crash() -> None:
    rows = _rows_from_feed("<rss><channel><item><id>KAP2U</id>")
    assert rows == []


def test_stock_feed_non_matching_product_is_ignored() -> None:
    row = {
        "sku": "OUTROSKU",
        "link": "https://megacentereletronicos.com.br/produto/outro-produto",
        "stock": "99",
    }
    assert not _match_row(row, page_url=PRODUCT_URL, sku="KAP2U", gtin="", name="Controle Gamer USB Kap-2U")


def test_stock_feed_zero_quantity_is_preserved() -> None:
    row = {"sku": "KAP2U", "stock": "0"}
    qty, source = _quantity_from_row(row)
    assert qty == "0"
    assert source == "stock"
