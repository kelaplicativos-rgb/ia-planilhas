import pandas as pd

from bling_app_zero.core.shared_price_calculator import apply_shared_pricing


def test_reajuste_rapido_reflete_acrescimo_e_promocional():
    df = pd.DataFrame([{'Preco': '56,00'}])
    config = {
        'enabled': True,
        'quick_reprice_mode': 'markup',
        'quick_markup_percent': 10.0,
        'marketplace_fee_percent': 0.0,
        'freight_cost': 0.0,
        'promo_discount_percent': 4.0,
    }

    out = apply_shared_pricing(df, 'Preco', config=config)

    assert out.loc[0, 'Preço de venda'] == 'R$ 61,60'
    assert out.loc[0, 'Preço promocional'] == 'R$ 59,14'


def test_reajuste_rapido_reflete_campos_fixos():
    df = pd.DataFrame([{'Preco': '100,00'}])
    config = {
        'enabled': True,
        'quick_reprice_mode': 'markup',
        'quick_markup_percent': 10.0,
        'marketplace_fee_percent': 5.0,
        'freight_cost': 2.0,
        'promo_discount_percent': 0.0,
    }

    out = apply_shared_pricing(df, 'Preco', config=config)

    assert out.loc[0, 'Preço de venda'] == 'R$ 117,00'
