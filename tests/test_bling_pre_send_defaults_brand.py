from __future__ import annotations

from bling_app_zero.core.bling_pre_send_defaults import apply_product_send_defaults


def test_presend_keeps_unknown_brand_inferred_from_title() -> None:
    row = {'Nome': 'Carregador Turbo Zorplax ZP-100', 'Marca': '', 'Código': '7891234567890'}

    fixed = apply_product_send_defaults(row)

    assert fixed['Marca'] == 'Zorplax'


def test_presend_keeps_imenso_inferred_from_title() -> None:
    row = {'Nome': 'Fone de Ouvido para Iphone Imenso IMS-871L', 'Marca': '', 'Código': '7899988478719'}

    fixed = apply_product_send_defaults(row)

    assert fixed['Marca'] == 'Imenso'


def test_presend_rejects_model_code_as_brand() -> None:
    row = {'Nome': 'Controle Sem Fio KP-4015', 'Marca': 'KP-4015', 'Código': '7891234567890'}

    fixed = apply_product_send_defaults(row)

    assert fixed['Marca'] == 'Genérico'
