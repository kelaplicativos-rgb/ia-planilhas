from __future__ import annotations

from bling_app_zero.core.product_persistence_check import missing_product_fields, product_persistence_flags


def test_volumes_itens_por_caixa_and_images_do_not_block_required_persistence() -> None:
    saved = {
        'nome': 'Produto teste',
        'codigo': 'SKU-1',
        'preco': 10,
        'descricaoCurta': 'Produto teste',
        'marca': 'Genérico',
        'categoria': {'id': 123},
        'pesoLiquido': 0.3,
        'pesoBruto': 0.3,
        'dimensoes': {'largura': 11, 'altura': 2, 'profundidade': 16},
        'volumes': 0,
        'itensPorCaixa': 0,
        'midia': {'imagens': {'externas': [], 'internas': [], 'imagensURL': []}},
    }

    flags = product_persistence_flags(saved)

    assert flags['volumes'] is False
    assert flags['itensPorCaixa'] is False
    assert flags['imagens'] is False
    assert missing_product_fields(saved) == []


def test_missing_core_fields_still_block_api_send() -> None:
    saved = {
        'codigo': 'SKU-1',
        'preco': 10,
        'marca': 'Genérico',
        'categoria': {'id': 123},
    }

    missing = missing_product_fields(saved)

    assert 'nome' in missing
    assert 'descricaoCurta' in missing
    assert 'volumes' not in missing
    assert 'itensPorCaixa' not in missing
    assert 'imagens' not in missing
