from __future__ import annotations

from bling_app_zero.core.site_engines.stock_value_engine import extract_real_stock_value

MEGA_CENTER_URL = "https://megacentereletronicos.com.br"
MEGA_CENTER_PRODUCT_URL = f"{MEGA_CENTER_URL}/produto/produto-simulado"


def _simulate_stock(body: str) -> tuple[str, str, str]:
    result = extract_real_stock_value(body, page_url=MEGA_CENTER_PRODUCT_URL)
    return result.quantity, result.source, result.confidence


def test_megacenter_json_inventory_level() -> None:
    html = '<script type="application/ld+json">{"@type":"Product","offers":{"inventoryLevel":{"value":17}}}</script><button>Comprar</button>'
    stock, source, confidence = _simulate_stock(html)
    assert stock == "17"
    assert source == "json"
    assert confidence == "alta"


def test_megacenter_html_data_stock() -> None:
    html = '<button data-stock="23">Comprar</button>'
    stock, source, confidence = _simulate_stock(html)
    assert stock == "23"
    assert source == "html_attrs"
    assert confidence == "alta"


def test_megacenter_script_stock_quantity() -> None:
    html = '<script>window.PRODUCT = {stock_quantity: 9};</script>'
    stock, source, confidence = _simulate_stock(html)
    assert stock == "9"
    assert source == "scripts"
    assert confidence == "alta"


def test_megacenter_visible_text_stock() -> None:
    html = '<p>Estoque disponível: 14 unidades</p>'
    stock, source, confidence = _simulate_stock(html)
    assert stock == "14"
    assert source == "texto"
    assert confidence == "alta"


def test_megacenter_out_of_stock_returns_zero() -> None:
    html = '<p>Produto indisponível no momento. Sem estoque.</p>'
    stock, source, confidence = _simulate_stock(html)
    assert stock == "0"
    assert source == "texto_indisponivel"
    assert confidence == "alta"


def test_megacenter_available_without_quantity_returns_one() -> None:
    html = '<button>Comprar</button>'
    stock, source, confidence = _simulate_stock(html)
    assert stock == "1"
    assert source == "fallback_disponivel_sem_quantidade"
    assert confidence == "baixa"
