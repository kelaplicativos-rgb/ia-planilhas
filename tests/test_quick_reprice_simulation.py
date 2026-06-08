import pandas as pd
import pytest

from bling_app_zero.core.shared_price_calculator import apply_shared_pricing


def _price_out(base='100,00', **overrides):
    config = {
        'enabled': True,
        'quick_reprice_mode': 'markup',
        'quick_markup_percent': 0.0,
        'marketplace_fee_percent': 0.0,
        'other_sale_fees_percent': 0.0,
        'freight_cost': 0.0,
        'marketplace_fixed_fee': 0.0,
        'quick_fixed_addition': 0.0,
        'promo_discount_percent': 0.0,
    }
    config.update(overrides)
    df = pd.DataFrame([{'Preco': base}])
    out = apply_shared_pricing(df, 'Preco', config=config)
    return out.loc[0, 'Preço de venda'], out.loc[0, 'Preço promocional']


def test_reajuste_rapido_reflete_acrescimo_e_promocional():
    venda, promocional = _price_out('56,00', quick_markup_percent=10.0, promo_discount_percent=4.0)

    assert venda == 'R$ 61,60'
    assert promocional == 'R$ 59,14'


@pytest.mark.parametrize(
    'campo,valor,esperado',
    [
        ('quick_markup_percent', 10.0, 'R$ 110,00'),
        ('marketplace_fee_percent', 5.0, 'R$ 105,00'),
        ('other_sale_fees_percent', 7.0, 'R$ 107,00'),
        ('freight_cost', 8.0, 'R$ 108,00'),
        ('marketplace_fixed_fee', 3.0, 'R$ 103,00'),
        ('quick_fixed_addition', 2.5, 'R$ 102,50'),
    ],
)
def test_cada_campo_da_calculadora_reflete_no_preco_de_venda(campo, valor, esperado):
    venda, promocional = _price_out('100,00', **{campo: valor})

    assert venda == esperado
    assert promocional == ''


def test_todos_os_percentuais_somam_no_preco_de_venda():
    venda, promocional = _price_out(
        '100,00',
        quick_markup_percent=10.0,
        marketplace_fee_percent=5.0,
        other_sale_fees_percent=2.0,
    )

    assert venda == 'R$ 117,00'
    assert promocional == ''


def test_todos_os_campos_fixos_somam_no_preco_de_venda():
    venda, promocional = _price_out(
        '100,00',
        freight_cost=8.0,
        marketplace_fixed_fee=3.0,
        quick_fixed_addition=2.5,
    )

    assert venda == 'R$ 113,50'
    assert promocional == ''


def test_percentuais_e_fixos_somam_e_promocional_desconta_do_preco_final():
    venda, promocional = _price_out(
        '100,00',
        quick_markup_percent=10.0,
        marketplace_fee_percent=5.0,
        other_sale_fees_percent=2.0,
        freight_cost=8.0,
        marketplace_fixed_fee=3.0,
        quick_fixed_addition=2.5,
        promo_discount_percent=4.0,
    )

    assert venda == 'R$ 130,50'
    assert promocional == 'R$ 125,28'


def test_reajuste_linha_a_linha_com_valores_brasileiros():
    df = pd.DataFrame([{'Preco': '56,00'}, {'Preco': '100,50'}, {'Preco': '0,00'}])
    config = {
        'enabled': True,
        'quick_reprice_mode': 'markup',
        'quick_markup_percent': 10.0,
        'promo_discount_percent': 4.0,
    }

    out = apply_shared_pricing(df, 'Preco', config=config)

    assert list(out['Preço de venda']) == ['R$ 61,60', 'R$ 110,55', '']
    assert list(out['Preço promocional']) == ['R$ 59,14', 'R$ 106,13', '']


def test_sem_reajuste_mantem_preco_base_e_promocional_vazio():
    venda, promocional = _price_out('56,00')

    assert venda == 'R$ 56,00'
    assert promocional == ''
