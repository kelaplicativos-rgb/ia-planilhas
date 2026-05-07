from __future__ import annotations

from bs4 import BeautifulSoup

from bling_app_zero.core.site_engines.estoque_fast_crawler import _json_ld_products, _stock_from_sources

MEGA_CENTER_URL = "https://megacentereletronicos.com.br"
MEGA_CENTER_PRODUCT_URL = "https://megacentereletronicos.com.br/produto/produto-simulado"


def _simulate_stock(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    products = _json_ld_products(soup)
    product = products[0] if products else {}
    full_text = soup.get_text(" ", strip=True)
    return _stock_from_sources(soup, product if isinstance(product, dict) else {}, full_text)


def test_megacenter_json_ld_inventory_level() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Produto Mega Center Simulado",
          "sku": "MC-001",
          "offers": {
            "@type": "Offer",
            "availability": "https://schema.org/InStock",
            "inventoryLevel": {"@type": "QuantitativeValue", "value": 17}
          }
        }
        </script>
      </head>
      <body><button>Comprar</button></body>
    </html>
    """
    stock, source = _simulate_stock(html)
    assert stock == "17"
    assert source == "json_ld"


def test_megacenter_html_data_stock() -> None:
    html = """
    <html>
      <body>
        <h1>Produto Mega Center Simulado</h1>
        <button data-stock="23">Comprar</button>
      </body>
    </html>
    """
    stock, source = _simulate_stock(html)
    assert stock == "23"
    assert source == "html_attrs"


def test_megacenter_script_stock_quantity() -> None:
    html = """
    <html>
      <body>
        <h1>Produto Mega Center Simulado</h1>
        <script>
          window.__PRODUCT__ = { sku: "MC-002", stock_quantity: 9 };
        </script>
      </body>
    </html>
    """
    stock, source = _simulate_stock(html)
    assert stock == "9"
    assert source == "scripts"


def test_megacenter_visible_text_stock() -> None:
    html = """
    <html>
      <body>
        <h1>Produto Mega Center Simulado</h1>
        <p>Estoque disponível: 14 unidades</p>
      </body>
    </html>
    """
    stock, source = _simulate_stock(html)
    assert stock == "14"
    assert source == "texto"


def test_megacenter_out_of_stock_returns_zero() -> None:
    html = """
    <html>
      <body>
        <h1>Produto Mega Center Simulado</h1>
        <p>Produto indisponível no momento. Sem estoque.</p>
      </body>
    </html>
    """
    stock, source = _simulate_stock(html)
    assert stock == "0"
    assert source == "texto_indisponivel"


def test_megacenter_available_without_real_quantity_falls_back_to_one() -> None:
    html = """
    <html>
      <body>
        <h1>Produto Mega Center Simulado</h1>
        <button>Comprar</button>
      </body>
    </html>
    """
    stock, source = _simulate_stock(html)
    assert stock == "1"
    assert source == "fallback_disponivel_sem_quantidade"
